"""TulipScript: the grammar accepts only what it should, the canonical
form round-trips, and run() imports the right rows, keeps every value's
source cells, and rejects wrong programs without an answer key.

The helpers here are SMALL STAND-INS so this test does not depend on
helpers.py. The real helpers (section 9 of the spec) are tested by
tests/test_helpers.py."""
import datetime
import unicodedata

import tulipscript as ts
from sheets import Sheet


# ---------------------------------------------------------- stand-ins
def _text(v, loc):
    t = ' '.join(unicodedata.normalize('NFKC', str(v)).split())
    return (bool(t), t or None)


def _amount(v, loc):
    if isinstance(v, bool):
        return False, None
    if isinstance(v, (int, float)):
        return True, float(v)
    t = str(v).replace('€', '').replace('$', '').replace(' ', '')
    t = t.replace('.', '').replace(',', '.') if ',' in t else t
    try:
        return True, float(t)
    except ValueError:
        return False, None


def _currency(v, loc):
    t = str(v)
    for sign, code in (('€', 'EUR'), ('EUR', 'EUR'), ('$', 'USD')):
        if sign in t:
            return True, code
    return False, None


def _integer(v, loc):
    try:
        return True, int(str(v).split()[0])
    except ValueError:
        return False, None


def _date(v, loc):
    if isinstance(v, datetime.datetime):
        return True, v.date().isoformat()
    t = str(v)
    if len(t) == 10 and t[4] == '-':
        return True, t
    if len(t) == 10 and t[2] == '/':
        return True, '%s-%s-%s' % (t[6:], t[3:5], t[:2])
    return False, None


def _boolean(v, loc):
    t = str(v).strip().lower()
    if t in ('oui', 'yes', 'x', '1', 'true'):
        return True, True
    if t in ('non', 'no', '0', 'false'):
        return True, False
    return False, None


def _tax_included(v, loc):
    t = str(v).upper()
    if 'TTC' in t:
        return True, True
    if 'HT' in t:
        return True, False
    return False, None


def _nothing(v, loc):
    return False, None


HELPERS = dict((h, _nothing) for h in ts.HELPERS)
HELPERS.update(text=_text, amount=_amount, currency=_currency,
               integer=_integer, date=_date, boolean=_boolean,
               tax_included=_tax_included)
TOTALS = ('total', 'sous-total', 'итого', '合计')

PRICE_LIST = Sheet('Tarifs 2024', [
    ['TARIFS BOULANGERIE MARTIN 2024'],
    [],
    ['Réf', 'Désignation', 'Taille', 'Prix TTC', 'Stock', 'Famille'],
    ['B-12', 'Baguette tradition', '250 g', 1.3, 40, 'Pains'],
    ['B-13', 'Pain de campagne', '500 g', 3.2, 12, 'Pains'],
    [],
    ['V-01', 'Croissant', None, 1.1, 80, 'Viennoiseries'],
    ['Réf', 'Désignation', 'Taille', 'Prix TTC', 'Stock', 'Famille'],
    ['V-02', 'Pain au chocolat', None, 1.25, 60, 'Viennoiseries'],
    [None, 'TOTAL', None, 6.85, 192, None],
])

GOOD = """target('products')
header(3)
keep(filled('A'))
out.sku = text(col('A'))
out.name = text(col('B'))
out.variant = text(col('C'))
out.category = text(col('F'))
out.price = amount(col('D'))
out.tax_included = tax_included(header_of('D'))
out.stock = integer(col('E'))"""


def run(text, sheet=PRICE_LIST, targets=('products', 'services')):
    return ts.run(ts.parse(text), sheet, HELPERS, 'fr-FR', targets, TOTALS)


def test_round_trip():
    for text in [GOOD, "refuse('missing_required:price')",
                 "target('invoice_ledger')\nheader(1)\n"
                 "keep(not_value('A', 'N°'))\n"
                 "out.number = text(col('A'))\nout.date = date(col('B'))\n"
                 "out.total = amount(col('C'))\n"
                 "out.status = lookup(col('D'), "
                 "{'Payée': 'paid', 'En attente': 'unpaid'})"]:
        once = ts.canonical(text)
        assert ts.canonical(once) == once
    # the canonical form uses schema order and single quotes
    assert ts.canonical(GOOD).splitlines()[0] == "target('products')"


def test_imports_the_right_rows():
    # fields must come in schema order: price before name is refused
    try:
        ts.parse("target('products')\nheader(3)\n"
                 "out.price = amount(col('D'))\nout.name = text(col('B'))")
        raise AssertionError('field order must be enforced')
    except ts.TulipError as e:
        assert e.code == 'field_order'
    text = GOOD
    res = run(text)
    assert res.status == 'imported', (res.problems, res.warnings)
    assert [r['sku'] for r in res.rows] == ['B-12', 'B-13', 'V-01', 'V-02']
    assert res.rows[0] == {'sku': 'B-12', 'name': 'Baguette tradition',
                           'variant': '250 g', 'category': 'Pains',
                           'price': 1.3, 'tax_included': True,
                           'stock': 40}
    assert res.rows[2]['variant'] is None
    assert res.row_numbers == [4, 5, 7, 9]      # the repeated header
    #                                              row 8 was skipped
    assert res.dropped == [10]                   # the TOTAL row
    # every value points at the cell it came from
    assert res.sources[0]['price'] == [(4, 'D')]
    assert res.sources[0]['tax_included'] == [(3, 'D')]    # header cell
    for record, sources in zip(res.rows, res.sources):
        for fname, cells in sources.items():
            assert cells, fname


def test_totals_row_is_caught_without_answer_key():
    # forgetting the filter imports "TOTAL" as a product - rejected
    text = GOOD.replace("keep(filled('A'))\n", "")
    res = run(text)
    assert res.status == 'rejected'
    assert any(p.startswith('totals_row_imported') for p in res.problems)


def test_dropping_real_data_is_caught():
    # filtering on the size column drops two real products
    text = GOOD.replace("keep(filled('A'))", "keep(filled('C'))")
    res = run(text)
    assert any(p.startswith('dropped_data_rows') for p in res.problems), \
        res.problems


def test_sections_and_unpivot():
    sheet = Sheet('Pizzas', [
        ['Pizza', 'Petite', 'Moyenne', 'Grande'],
        ['CLASSIQUES'],
        ['Margherita', '8,50 €', '11,00 €', '14,00 €'],
        ['Regina', '9,50 €', None, '15,50 €'],
        ['SPÉCIALITÉS'],
        ['Calzone', None, '13,00 €', None],
    ])
    text = """target('products')
header(1)
sections()
unpivot('B', 'C', 'D')
out.name = text(col('A'))
out.variant = text(col('name'))
out.category = text(col('section'))
out.price = amount(col('value'))
out.currency = currency(col('value'))"""
    res = run(text, sheet)
    assert res.status == 'imported', res.problems
    got = [(r['name'], r['variant'], r['category'], r['price'])
           for r in res.rows]
    assert got == [('Margherita', 'Petite', 'CLASSIQUES', 8.5),
                   ('Margherita', 'Moyenne', 'CLASSIQUES', 11.0),
                   ('Margherita', 'Grande', 'CLASSIQUES', 14.0),
                   ('Regina', 'Petite', 'CLASSIQUES', 9.5),
                   ('Regina', 'Grande', 'CLASSIQUES', 15.5),
                   ('Calzone', 'Moyenne', 'SPÉCIALITÉS', 13.0)], got
    assert res.sources[0]['variant'] == [(1, 'B')]
    assert res.sources[0]['category'] == [(2, 'A')]


def test_part_join_first_lookup():
    sheet = Sheet('Factures', [
        ['N°', 'Date', 'Client', 'Montant HT', 'Montant TTC', 'Statut',
         'Contact'],
        ['F-001', '15/03/2024', 'Hôtel du Lac', '100,00', '120,00',
         'Payée', 'Marie Dupont'],
        ['F-002', '20/03/2024', 'Café Central', '50,00', None,
         'En attente', 'Luc Martin'],
    ])
    text = """target('invoice_ledger')
header(1)
out.number = text(col('A'))
out.date = date(col('B'))
out.client = text(join(' - ', col('C'), part(col('G'), ' ', -1)))
out.total = first(amount(col('E')), amount(col('D')))
out.status = lookup(col('F'), {'payée': 'paid', 'En attente': 'unpaid'})"""
    res = run(text, sheet, ('invoice_ledger',))
    assert res.status == 'imported', res.problems
    assert res.rows[0]['client'] == 'Hôtel du Lac - Dupont'
    assert res.rows[0]['total'] == 120.0 and res.rows[1]['total'] == 50.0
    assert [r['status'] for r in res.rows] == ['paid', 'unpaid']
    # a lookup key that never occurs in the sheet is an invention
    bad = text.replace("'En attente': 'unpaid'",
                       "'En attente': 'unpaid', 'Annulée': 'cancelled'")
    res = run(bad, sheet, ('invoice_ledger',))
    assert any(p.startswith('lookup_key_not_in_source') for p in
               res.problems)


def test_grammar_rejects_everything_else():
    bad = {
        "import os": 'statement_not_allowed',
        "target('products')\nheader(1)\nout.name = text(col('B'))\n"
        "out.price = amount(col('C'))\nexec('x')": 'unknown_statement',
        "target('products')\nheader(1)\nout.name = col('B').strip()\n"
        "out.price = amount(col('C'))": 'expected_call',
        "target('products')\nheader(1)\nout.name = text(col('B'))": \
        'required_not_assigned',
        "target('products')\nheader(1)\nout.name = text(col('B'))\n"
        "out.price = text(col('C'))": 'wrong_kind',
        "target('products')\nheader(1)\nout.name = text(col('B'))\n"
        "out.price = amount(col('C'))\nout.owner = text(col('D'))":
        'unknown_field',
        "header(1)\ntarget('products')": 'out_of_order',
        "target('products')\nrefuse('not_a_table')":
        'refuse_must_be_alone',
        "refuse('because I said so')": 'bad_refusal',
        "target('weather')\nheader(1)": 'unknown_target',
        "target('products')\nheader(1)\nout.name = text(col('BB'))\n"
        "out.price = amount(col('C'))": 'bad_column',
        "target('products')\nheader(1)\nout.name = text(col(x='B'))\n"
        "out.price = amount(col('C'))": 'keywords_not_allowed',
        "target('products')\nheader(1)\nout.name = text(col('B'))\n"
        "out.price = amount(col('C'))\nout.active = lookup(col('D'), "
        "{'oui': True, 'non': 'no'})": 'mixed_lookup_values',
        "target('bookings')\nheader(1)\nout.date = date(col('A'))\n"
        "out.start_time = time(col('B'))\nout.status = lookup(col('C'), "
        "{'ok': 'approved'})": 'wrong_kind',
        "target('products')\nheader(1)\nout.name = text(col('section'))\n"
        "out.price = amount(col('C'))": 'bad_column',
        "target('products')\nheader(1)\nkeep(not_value('A', '" + 'x' * 70
        + "'))\nout.name = text(col('B'))\nout.price = amount(col('C'))":
        'string_too_long',
        "target('products')\nheader(1)\nout.name = text('Pain')\n"
        "out.price = amount(col('C'))": 'expected_call',
        "lambda: 1": 'expected_call',
        "target('products')\nheader(1)\nout.name = text(header_of('B'))\n"
        "out.price = amount(col('C'))": 'constant_field',
        "target('products')\nheader(1)\nunpivot('C', 'B')\n"
        "out.name = text(col('A'))\nout.price = amount(col('value'))":
        'unpivot_order',
        "target('products'": 'syntax',
    }
    for text, code in bad.items():
        try:
            ts.parse(text)
        except ts.TulipError as e:
            assert e.code == code, (text, e.code, code)
        else:
            raise AssertionError('accepted: %r' % text)


def test_refusal_and_offered_targets():
    res = run("refuse('no_matching_target')")
    assert res.status == 'refused'
    text = ("target('staff')\nheader(3)\nout.name = text(col('B'))")
    res = run(text)                          # staff was not offered
    assert res.problems == ['target_not_offered']


def test_parse_failures_are_counted():
    sheet = Sheet('Stock', [
        ['Produit', 'Prix'], ['Pain', '1,30 €'], ['Tarte', 'sur demande'],
        ['Gâteau', '12,00 €']])
    text = ("target('products')\nheader(1)\nout.name = text(col('A'))\n"
            "out.price = amount(col('B'))")
    res = run(text, sheet)
    # 1 row of 3 has no readable price: more than 2%, so rejected
    assert 'required_missing' in res.problems
    assert res.skipped == [(3, 'unreadable:price')]


def test_format_of_and_first_do_not_count_replaced_failures():
    sheet = Sheet('Prices', [['Item', 'Price'], ['Bread', 1.3],
                             ['Cake', 12.0]],
                  formats=[[None, None], ['General', '0.00 €'],
                           ['General', '0.00 €']])
    text = ("target('products')\nheader(1)\nout.name = text(col('A'))\n"
            "out.price = amount(col('B'))\nout.currency = "
            "first(currency(col('B')), currency(format_of('B')))")
    res = run(text, sheet)
    # currency(1.3) fails on every row, but format_of('B') answers:
    # that is not a parse failure
    assert res.status == 'imported', (res.problems, res.warnings)
    assert [r['currency'] for r in res.rows] == ['EUR', 'EUR']
    assert res.sources[0]['currency'] == [(2, 'B')]


def test_notes_rows_need_no_filter_but_wrong_columns_are_caught():
    sheet = Sheet('Tarifs', [
        ['Produit', 'Prix', 'Remarque'],
        ['Pain', '1,30 €', None], ['Tarte', '12,00 €', 'sur commande'],
        ['Gâteau', '–', None], ['Éclair', '2,10 €', None],
        ["Prix valables jusqu'au 31/12", None, None]])
    good = ("target('products')\nheader(1)\nout.name = text(col('A'))\n"
            "out.price = amount(col('B'))")
    res = run(good, sheet)
    # the notes line and the '–' placeholder are empty, not errors
    assert res.status == 'imported_with_warnings', res.problems
    assert [r['name'] for r in res.rows] == ['Pain', 'Tarte', 'Éclair']
    assert res.empty == [4, 6]
    # pointing the price at the notes column: mostly empty -> rejected
    wrong = good.replace("amount(col('B'))", "amount(col('C'))")
    assert 'mostly_empty' in run(wrong, sheet).problems


def test_totals_words_respect_word_boundaries():
    assert ts.is_total_cell('Sous-total Pains', ['sous-total'])
    assert ts.is_total_cell('Итого:', ['итого'])
    assert ts.is_total_cell('合计', ['合计'])
    assert not ts.is_total_cell('小计算器', ['小计'])
    assert not ts.is_total_cell('योगेश कुमार', ['योग'])
    assert ts.is_total_cell('योग', ['योग'])
    # a client called "Total Fitness" is not a totals row ...
    assert not ts.is_totals_row(['Total Fitness Ltd', 'Marie Roux',
                                 '+41 22 123 45 67'], ['total'])
    # ... but "TOTAL | 412,50 €" is
    assert ts.is_totals_row([None, 'TOTAL', '412,50 €', 192], ['total'])
    try:
        ts.run(ts.parse("refuse('not_a_table')"), PRICE_LIST, HELPERS)
        raise AssertionError('totals words must be required')
    except ValueError:
        pass


def test_part_reads_the_nfkc_form():
    sheet = Sheet('Menu', [['Plat', 'Prix'],
                           ['Pizza\u00a0-\u00a0Grande', '9,50 €'],
                           ['Pizza - Petite', '7,00 €']])
    text = ("target('products')\nheader(1)\n"
            "out.name = text(part(col('A'), ' - ', 0))\n"
            "out.variant = text(part(col('A'), ' - ', 1))\n"
            "out.price = amount(col('B'))")
    res = run(text, sheet)
    assert res.status == 'imported', res.problems
    assert [r['variant'] for r in res.rows] == ['Grande', 'Petite']


def test_section_rows_must_be_consistent():
    sheet = Sheet('Soins', [
        ['Prestation', 'Durée', 'Prix'],
        ['COUPES'], ['Coupe femme', '45 min', '38 €'],
        [None, 'COLORATION'], ['Couleur', '60 min', '55 €']])
    text = ("target('services')\nheader(1)\nsections()\n"
            "out.name = text(col('A'))\nout.category = text(col('section'))"
            "\nout.price = amount(col('C'))")
    res = run(text, sheet, ('services',))
    assert 'sections_in_several_columns' in res.problems
    assert res.sections == [2, 4]


def test_plausibility_rules():
    import datetime as dt
    days = [dt.datetime(2024, 3, d) for d in (4, 5, 6)]
    sheet = Sheet('RDV', [['Date', 'Client']] +
                  [[d, 'Client %d' % i] for i, d in enumerate(days)])
    text = ("target('bookings')\nheader(1)\nout.date = date(col('A'))\n"
            "out.start_time = time(col('A'))\nout.client = text(col('B'))")
    helpers = dict(HELPERS, time=lambda v, loc: (True, v.strftime('%H:%M')))
    res = ts.run(ts.parse(text), sheet, helpers, 'fr-FR', ('bookings',),
                 TOTALS)
    # time() on date-only cells gives 00:00 on every row: rejected
    assert 'midnight_times' in res.problems
    ledger = Sheet('Factures', [['N°', 'Date', 'Montant'],
                                ['F-1', '01/03/2024', '10,00'],
                                ['F-1', '02/03/2024', '20,00'],
                                ['F-2', '03/03/2024', '30,00']])
    text = ("target('invoice_ledger')\nheader(1)\n"
            "out.number = text(col('A'))\nout.date = date(col('B'))\n"
            "out.total = amount(col('C'))")
    res = run(text, ledger, ('invoice_ledger',))
    assert 'duplicate_numbers' in res.problems
