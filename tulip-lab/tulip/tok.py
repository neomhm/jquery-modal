"""
tok.py - Tulip's tokenizer, trained from scratch. Same design as the
Extractor's tokenizer (byte-level BPE, NFKC, one piece per CJK character,
digit and punctuation mark); only the special tokens differ.

Why these choices:
  * byte-level BPE  -> never an unknown character, in any language
  * NFKC            -> full-width digits (１２３), ㈱ and non-breaking
                       spaces become their plain form; the runtime
                       compares cells and lookup keys in NFKC too
  * one piece per CJK character, digit and punctuation mark
                    -> headers and cell values in any of the ten
                       languages are read piece by piece, and every
                       program symbol - ( ) ' . = - is its own token
Tulip refers to columns by letter (col('D')), so it never has to copy
header text; the only free text it writes is inside lookup() keys,
not_value() and separators.
"""
from tokenizers import (Tokenizer, Regex, decoders, models, normalizers,
                        pre_tokenizers, trainers)

SPECIALS = ["[PAD]", "[UNK]", "[PROGRAM]", "[END]"]
PAD, UNK, PROGRAM, END = range(4)

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
    """texts: previews AND programs, from all ten languages."""
    tok = new_tokenizer()
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        min_frequency=2,
        special_tokens=SPECIALS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=False)
    tok.train_from_iterator(texts, trainer=trainer)
    assert tok.token_to_id("[PAD]") == PAD
    assert tok.token_to_id("[END]") == END
    return tok


def encode(tok, text):
    return tok.encode(text, add_special_tokens=False).ids


def decode(tok, ids):
    """Token ids -> text, stopping at [END]. The result equals the NFKC
    form of the text that was encoded."""
    if END in ids:
        ids = ids[:ids.index(END)]
    return tok.decode([i for i in ids if i > END], skip_special_tokens=False)
