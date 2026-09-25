"""
model.py - the Extractor: a bidirectional transformer ENCODER.

Daisy reads left to right and writes the next piece. The Extractor
reads the whole chunk at once - every token sees the words before AND
after it - and then puts a label on every token. It never writes text,
so it cannot invent a value: whatever it marks is a slice of the chunk.

Same building blocks as Daisy (RMSNorm, SwiGLU, no biases, PyTorch's
scaled_dot_product_attention) with two changes:
  * no causal mask: attention looks both ways; padding is masked out
  * rotary positions (RoPE) instead of a learned position table, so
    position is part of how tokens compare, and lengths up to max_len
    work without a table that must match
Heads on top:
  * token head   - one BIO label per token (the extraction)
  * doc head     - what kind of document the chunk comes from (the
                   Sorter, folded in)
  * lang head    - which of the ten languages the chunk is in
  * mlm head     - only for pretraining: guess the hidden tokens
"""
import math
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
from torch.nn import functional as F


@dataclass
class Config:
    vocab_size: int
    d_model: int = 384
    n_layer: int = 8
    n_head: int = 6
    ffn_hidden: int = 1024       # SwiGLU inner size
    max_len: int = 1024          # longest sequence in one pass
    dropout: float = 0.1
    n_labels: int = 51           # 1 + 2 x number of span types
    n_doc_types: int = 11
    n_langs: int = 10
    rope_base: float = 10000.0


def rope_tables(head_dim, max_len, base, device=None):
    inv = 1.0 / (base ** (torch.arange(0, head_dim, 2, device=device)
                          .float() / head_dim))
    t = torch.arange(max_len, device=device).float()
    freqs = torch.outer(t, inv)                       # (T, D/2)
    return torch.cos(freqs), torch.sin(freqs)


def apply_rope(x, cos, sin):
    """x: (B, H, T, D). Rotate pairs (x1, x2) by the position angle."""
    T = x.shape[2]
    cos, sin = cos[:T][None, None], sin[:T][None, None]
    x1, x2 = x[..., 0::2], x[..., 1::2]
    out = torch.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), dim=-1)
    return out.flatten(-2).type_as(x)


class Attention(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.n_head = c.n_head
        self.dropout = c.dropout
        self.qkv = nn.Linear(c.d_model, 3 * c.d_model, bias=False)
        self.out = nn.Linear(c.d_model, c.d_model, bias=False)

    def forward(self, x, keep, cos, sin):
        B, T, C = x.shape
        h = self.n_head
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, h, C // h).transpose(1, 2)
        k = k.view(B, T, h, C // h).transpose(1, 2)
        v = v.view(B, T, h, C // h).transpose(1, 2)
        q, k = apply_rope(q, cos, sin), apply_rope(k, cos, sin)
        # keep: (B, T) True for real tokens. Every query may look at
        # every real key, before or after it.
        mask = keep[:, None, None, :]
        p = self.dropout if self.training else 0.0
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=mask,
                                           dropout_p=p)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.out(y)


class SwiGLU(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.propose = nn.Linear(c.d_model, c.ffn_hidden, bias=False)
        self.gate = nn.Linear(c.d_model, c.ffn_hidden, bias=False)
        self.back = nn.Linear(c.ffn_hidden, c.d_model, bias=False)

    def forward(self, x):
        return self.back(self.propose(x) * F.silu(self.gate(x)))


class Block(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.norm1 = nn.RMSNorm(c.d_model)
        self.attn = Attention(c)
        self.norm2 = nn.RMSNorm(c.d_model)
        self.ffn = SwiGLU(c)
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x, keep, cos, sin):
        x = x + self.drop(self.attn(self.norm1(x), keep, cos, sin))
        x = x + self.drop(self.ffn(self.norm2(x)))
        return x


class Extractor(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.config = c
        self.embed = nn.Embedding(c.vocab_size, c.d_model)
        self.drop = nn.Dropout(c.dropout)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.n_layer))
        self.final_norm = nn.RMSNorm(c.d_model)
        self.token_head = nn.Linear(c.d_model, c.n_labels, bias=False)
        self.doc_head = nn.Linear(c.d_model, c.n_doc_types, bias=False)
        self.lang_head = nn.Linear(c.d_model, c.n_langs, bias=False)
        # MLM head: small transform, then scores against the embedding
        # table itself (tied weights - no second 48k x d matrix)
        self.mlm_dense = nn.Linear(c.d_model, c.d_model, bias=False)
        self.mlm_norm = nn.RMSNorm(c.d_model)
        cos, sin = rope_tables(c.d_model // c.n_head, c.max_len,
                               c.rope_base)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)
        self.apply(self._init)
        # residual outputs start smaller so a deep stack stays stable
        for block in self.blocks:
            nn.init.normal_(block.attn.out.weight, 0.0,
                            0.02 / math.sqrt(2 * c.n_layer))
            nn.init.normal_(block.ffn.back.weight, 0.0,
                            0.02 / math.sqrt(2 * c.n_layer))

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, 0.0, 0.02)

    def forward(self, ids, keep):
        """ids: (B, T) token ids; keep: (B, T) bool, False = padding.
        Returns hidden states (B, T, d)."""
        T = ids.shape[1]
        assert T <= self.config.max_len, "cut long chunks into windows"
        x = self.drop(self.embed(ids))
        for block in self.blocks:
            x = block(x, keep, self.cos, self.sin)
        return self.final_norm(x)

    def token_logits(self, h):
        return self.token_head(h)

    def pooled(self, h, keep):
        w = keep.unsqueeze(-1).type_as(h)
        return (h * w).sum(1) / w.sum(1).clamp(min=1.0)

    def doc_logits(self, h, keep):
        return self.doc_head(self.pooled(h, keep))

    def lang_logits(self, h, keep):
        return self.lang_head(self.pooled(h, keep))

    def mlm_logits(self, h, positions):
        """positions: (N, 2) long tensor of (batch, time) of the masked
        tokens. Scores are computed ONLY there - computing 48k scores
        for every token would need gigabytes for nothing."""
        x = h[positions[:, 0], positions[:, 1]]
        x = self.mlm_norm(F.gelu(self.mlm_dense(x)))
        return x @ self.embed.weight.t()

    def count(self):
        total = sum(p.numel() for p in self.parameters())
        emb = self.embed.weight.numel()
        return total, total - emb


def mask_for_mlm(ids, keep, vocab_size, rate=0.2, first_normal=5,
                 generator=None):
    """BERT-style masking. Picks `rate` of the real tokens; of those
    80% become [MASK] (id 4), 10% a random normal token, 10% stay.
    Returns (new_ids, positions (N, 2), targets (N,))."""
    MASK = 4
    r = torch.rand(ids.shape, generator=generator, device=ids.device)
    chosen = (r < rate) & keep & (ids >= first_normal)
    positions = chosen.nonzero()
    targets = ids[chosen]
    new = ids.clone()
    how = torch.rand(targets.shape, generator=generator, device=ids.device)
    rand_tok = torch.randint(first_normal, vocab_size, targets.shape,
                             generator=generator, device=ids.device)
    replaced = torch.where(how < 0.8, torch.full_like(targets, MASK),
                           torch.where(how < 0.9, rand_tok, targets))
    new[chosen] = replaced
    return new, positions, targets


def save(path, model, tokenizer_json, meta):
    """One self-contained file: weights + settings + tokenizer + label
    lists + calibration. Nothing else is needed to use the model."""
    torch.save({"config": asdict(model.config),
                "state_dict": model.state_dict(),
                "tokenizer": tokenizer_json,
                "meta": meta}, path)


def load(path, device="cpu"):
    blob = torch.load(path, map_location=device, weights_only=False)
    model = Extractor(Config(**blob["config"]))
    model.load_state_dict(blob["state_dict"])
    model.to(device).eval()
    return model, blob["tokenizer"], blob["meta"]
