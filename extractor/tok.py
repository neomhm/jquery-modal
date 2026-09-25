"""
tok.py - the Extractor's tokenizer, trained from scratch, and the
function that turns character spans into one label per token.

Why these choices:
  * byte-level BPE  -> never an unknown character, in any language
  * NFKC            -> full-width digits (１２３), ㈱, non-breaking
                       spaces all become their plain form, while the
                       offsets still point into the ORIGINAL text
  * every Chinese / Japanese / Korean character is its own piece
                    -> a name that runs straight into the next word
                       (株式会社サクラは, 한빛전자는) can still be cut
                       exactly at the character where it ends
  * every digit is its own piece
                    -> amounts, IDs and dates are read digit by digit
                       (the Daisy lesson: layout beats size)
  * every punctuation mark is its own piece, and a word keeps its
    combining marks (Hindi matras, Arabic harakat)
                    -> a value never ends in the middle of a token
"""
from tokenizers import (Tokenizer, Regex, decoders, models, normalizers,
                        pre_tokenizers, trainers)

SPECIALS = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
PAD, UNK, CLS, SEP, MASK = range(5)

# How text is cut BEFORE byte-level BPE learns its merges. Checked in
# order at every position; a single leading space stays glued on.
#   1. one Chinese / Japanese / Korean character
#   2. one digit (any script: 0-9, Arabic-Indic, Devanagari...)
#   3. a run of letters WITH their combining marks (keeps Hindi and
#      Arabic words whole) - but never CJK, so "ABC株式会社" splits
#   4. one punctuation mark or symbol ("»," is two pieces, not one)
#   5. a run of whitespace (newlines stay their own pieces)
PIECES = (r" ?[\p{Han}\p{Hiragana}\p{Katakana}\p{Hangul}]"
          r"| ?\p{N}"
          r"| ?[\p{L}\p{M}&&[^\p{Han}\p{Hiragana}\p{Katakana}\p{Hangul}]]+"
          r"| ?[^\s\p{L}\p{M}\p{N}]"
          r"|\s+")


def new_tokenizer():
    tok = Tokenizer(models.BPE())
    tok.normalizer = normalizers.NFKC()
    tok.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Split(Regex(PIECES), behavior="isolated"),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
    ])
    tok.decoder = decoders.ByteLevel()
    return tok


def train_tokenizer(texts, vocab_size):
    """texts: any iterable of strings (use a language-balanced mix)."""
    tok = new_tokenizer()
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        min_frequency=2,
        special_tokens=SPECIALS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=False)
    tok.train_from_iterator(texts, trainer=trainer)
    assert tok.token_to_id("[PAD]") == PAD
    assert tok.token_to_id("[MASK]") == MASK
    return tok


def encode(tok, text):
    """-> (ids, offsets). offsets[i] = (start, end, is_space) in the
    ORIGINAL text. For normal tokens the range is trimmed of the space
    that byte-level BPE glues to the front of a word. Tokens made only
    of whitespace (a newline, a double space) keep their raw range and
    is_space=True."""
    enc = tok.encode(text, add_special_tokens=False)
    offsets = []
    for a, b in enc.offsets:
        piece = text[a:b]
        core = piece.strip()
        if not core:
            offsets.append((a, b, True))
        else:
            lead = len(piece) - len(piece.lstrip())
            trail = len(piece) - len(piece.rstrip())
            offsets.append((a + lead, b - trail, False))
    return enc.ids, offsets


def token_labels(offsets, spans, cut, label_id, ignore=-100):
    """One label per token, BIO style.

    spans: (start, end, TYPE) in characters, never starting or ending
    with whitespace. cut: (start, end) ranges to ignore.
    label_id: {"O": 0, "B-S_NAME": 1, "I-S_NAME": 2, ...}.

    A normal token belongs to a span when their characters overlap.
    A whitespace token belongs to a span only when it sits strictly
    inside it (the newline in a two-line address) - it is then I-TYPE.
    """
    labels = [label_id["O"]] * len(offsets)
    for s, e, kind in spans:
        first = True
        for i, (a, b, space) in enumerate(offsets):
            if space:
                if s < a and b < e and not first:
                    labels[i] = label_id["I-" + kind]
                continue
            if a < e and b > s:
                labels[i] = label_id[("B-" if first else "I-") + kind]
                first = False
    for s, e in cut:
        for i, (a, b, space) in enumerate(offsets):
            if a < e and b > s:
                labels[i] = ignore
    return labels


def boundary_ok(offsets, s, e):
    """True when the span starts at a token start and ends at a token
    end - i.e. the model CAN return exactly this value. The build must
    report the share of spans for which this holds (target >= 99.5%)."""
    starts = {a for a, b, space in offsets if not space}
    ends = {b for a, b, space in offsets if not space}
    return s in starts and e in ends
