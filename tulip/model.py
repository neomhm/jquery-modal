"""
model.py - Tulip: a left-to-right transformer (a decoder, like Daisy)
that reads a sheet preview and writes a TulipScript program.

Same building blocks as Daisy - RMSNorm, SwiGLU, no biases, PyTorch's
scaled_dot_product_attention - with three changes:
  * rotary positions (RoPE) instead of a position table
  * a key/value cache, so writing each new token costs one token of
    work instead of re-reading the whole preview (a preview is usually
    1,000-3,000 tokens, a program about 150)
  * the output layer shares its weights with the input embedding
Sequence layout for training:  preview  [PROGRAM]  program  [END]
The loss is taken on the program and [END] only - Tulip is never
trained to write previews.
"""
import math
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
from torch.nn import functional as F

IGNORE = -100


@dataclass
class Config:
    vocab_size: int
    d_model: int = 512
    n_layer: int = 8
    n_head: int = 8
    ffn_hidden: int = 1408
    max_len: int = 4096
    dropout: float = 0.0
    rope_base: float = 10000.0


def rope_tables(head_dim, max_len, base):
    inv = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
    freqs = torch.outer(torch.arange(max_len).float(), inv)
    return torch.cos(freqs), torch.sin(freqs)


def apply_rope(x, cos, sin, start):
    """x: (B, H, T, D); positions start .. start+T-1."""
    T = x.shape[2]
    cos = cos[start:start + T][None, None]
    sin = sin[start:start + T][None, None]
    x1, x2 = x[..., 0::2], x[..., 1::2]
    out = torch.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), dim=-1)
    return out.flatten(-2).type_as(x)


class Attention(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.n_head, self.dropout = c.n_head, c.dropout
        self.qkv = nn.Linear(c.d_model, 3 * c.d_model, bias=False)
        self.out = nn.Linear(c.d_model, c.d_model, bias=False)

    def forward(self, x, cos, sin, cache=None, start=0):
        B, T, C = x.shape
        h = self.n_head
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, h, C // h).transpose(1, 2)
        k = k.view(B, T, h, C // h).transpose(1, 2)
        v = v.view(B, T, h, C // h).transpose(1, 2)
        q = apply_rope(q, cos, sin, start)
        k = apply_rope(k, cos, sin, start)
        if cache is not None:
            if 'k' in cache:
                k = torch.cat([cache['k'], k], dim=2)
                v = torch.cat([cache['v'], v], dim=2)
            cache['k'], cache['v'] = k, v
        p = self.dropout if self.training else 0.0
        if k.shape[2] == T:
            # training, or the first pass over the preview: causal
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True,
                                               dropout_p=p)
        elif T == 1:
            # one new token: it may look at everything before it
            y = F.scaled_dot_product_attention(q, k, v, dropout_p=p)
        else:
            raise ValueError("feed a cached model one token at a time")
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

    def forward(self, x, cos, sin, cache=None, start=0):
        x = x + self.drop(self.attn(self.norm1(x), cos, sin, cache, start))
        x = x + self.drop(self.ffn(self.norm2(x)))
        return x


class Tulip(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.config = c
        self.embed = nn.Embedding(c.vocab_size, c.d_model)
        self.drop = nn.Dropout(c.dropout)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.n_layer))
        self.final_norm = nn.RMSNorm(c.d_model)
        cos, sin = rope_tables(c.d_model // c.n_head, c.max_len,
                               c.rope_base)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)
        self.apply(self._init)
        for block in self.blocks:
            nn.init.normal_(block.attn.out.weight, 0.0,
                            0.02 / math.sqrt(2 * c.n_layer))
            nn.init.normal_(block.ffn.back.weight, 0.0,
                            0.02 / math.sqrt(2 * c.n_layer))

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, 0.0, 0.02)

    def hidden(self, ids, caches=None, start=0):
        """ids: (B, T). Returns the final hidden states (B, T, d)."""
        T = ids.shape[1]
        assert start + T <= self.config.max_len, "sequence too long"
        x = self.drop(self.embed(ids))
        for i, block in enumerate(self.blocks):
            x = block(x, self.cos, self.sin,
                      None if caches is None else caches[i], start)
        return self.final_norm(x)

    def forward(self, ids, caches=None, start=0):
        """ids: (B, T). Returns logits (B, T, vocab)."""
        return self.hidden(ids, caches, start) @ self.embed.weight.t()

    def loss(self, ids, labels):
        """Next-token loss on the program only. Scores are computed ONLY
        where a label exists: the preview is ~90% of every sequence, and
        24,000 scores per preview token would cost gigabytes for
        nothing."""
        h = self.hidden(ids[:, :-1])
        target = labels[:, 1:]
        keep = target != IGNORE
        logits = h[keep] @ self.embed.weight.t()
        return F.cross_entropy(logits.float(), target[keep])

    @torch.no_grad()
    def generate(self, prompt_ids, end_id, max_new=400, n=1,
                 temperature=0.0, top_p=0.95, generator=None):
        """Write n programs for one preview. temperature 0 = greedy (then
        n must be 1). Returns n lists of token ids, each cut before
        end_id. The preview is read once and its cache shared."""
        assert temperature > 0 or n == 1
        device = self.embed.weight.device
        caches = [dict() for _ in self.blocks]
        prompt = torch.tensor([prompt_ids], device=device)
        logits = self(prompt, caches, 0)[:, -1].float()
        for cache in caches:
            cache['k'] = cache['k'].expand(n, -1, -1, -1).contiguous()
            cache['v'] = cache['v'].expand(n, -1, -1, -1).contiguous()
        logits = logits.expand(n, -1)
        position = len(prompt_ids)
        outputs = [[] for _ in range(n)]
        done = [False] * n
        for _ in range(max_new):
            if temperature == 0:
                nxt = logits.argmax(-1)
            else:
                probs = torch.softmax(logits / temperature, -1)
                sorted_p, order = probs.sort(-1, descending=True)
                cut = sorted_p.cumsum(-1) - sorted_p > top_p
                sorted_p = sorted_p.masked_fill(cut, 0.0)
                pick = torch.multinomial(sorted_p, 1, generator=generator)
                nxt = order.gather(-1, pick).squeeze(-1)
            for i, t in enumerate(nxt.tolist()):
                if not done[i]:
                    if t == end_id:
                        done[i] = True
                    else:
                        outputs[i].append(t)
            if all(done) or position + 1 >= self.config.max_len:
                break
            logits = self(nxt.view(n, 1), caches, position)[:, -1].float()
            position += 1
        return outputs

    def count(self):
        total = sum(p.numel() for p in self.parameters())
        return total, total - self.embed.weight.numel()


def training_pair(prompt_ids, program_ids, program_token, end_token):
    """One training sequence and its labels:
    preview [PROGRAM] program [END]; labels only on program + [END]."""
    ids = list(prompt_ids) + [program_token] + list(program_ids) + \
        [end_token]
    labels = [IGNORE] * (len(prompt_ids) + 1) + list(program_ids) + \
        [end_token]
    return ids, labels


def save(path, model, tokenizer_json, meta):
    torch.save({"config": asdict(model.config),
                "state_dict": model.state_dict(),
                "tokenizer": tokenizer_json, "meta": meta}, path)


def load(path, device="cpu"):
    blob = torch.load(path, map_location=device, weights_only=False)
    model = Tulip(Config(**blob["config"]))
    model.load_state_dict(blob["state_dict"])
    model.to(device).eval()
    return model, blob["tokenizer"], blob["meta"]
