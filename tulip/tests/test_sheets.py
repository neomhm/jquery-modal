"""Sheets: real .xlsx and .csv files are read into grids, and the preview
text has exactly the fixed shape the model is trained on."""
import datetime
import os
import tempfile

import sheets


def _xlsx(path):
    import openpyxl
    book = openpyxl.Workbook()
    ws = book.active
    ws.title = 'Tarifs 2024'
    ws.append(['TARIFS BOULANGERIE MARTIN 2024'])
    ws.append([])
    ws.append(['Réf', 'Désignation', 'Prix TTC', 'Stock', 'Depuis'])
    ws.append(['B-12', 'Baguette | tradition', 1.3, 40,
               datetime.datetime(2024, 3, 15)])
    ws.append(['B-13', 'Pain de campagne\nau levain', 3.2, 12,
               datetime.datetime(2023, 1, 2)])
    for row in (4, 5):
        ws.cell(row=row, column=3).number_format = '0.00 €'
    other = book.create_sheet('Notes')
    other.append(['Anything'])
    book.save(path)


def test_xlsx_and_preview():
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, 'tarifs.xlsx')
    _xlsx(path)
    found = sheets.load(path)
    assert [s.name for s in found] == ['Tarifs 2024', 'Notes']
    sheet = found[0]
    assert sheet.rows[3][:4] == ['B-12', 'Baguette | tradition', 1.3, 40]
    assert sheet.rows[1] == []
    text = sheets.preview(sheet, ['products', 'services'], 'fr-FR')
    want = "\n".join([
        "TARGETS products | services",
        "LOCALE fr-FR",
        "SHEET 'Tarifs 2024' | rows 5 | columns A-E",
        "TYPES A:text B:text C:number D:integer E:date",
        "FORMATS C:'0.00 €'",
        "R1 A:TARIFS BOULANGERIE MARTIN 2024",
        "R3 A:Réf | B:Désignation | C:Prix TTC | D:Stock | E:Depuis",
        "R4 A:B-12 | B:Baguette ¦ tradition | C:1.3 | D:40 | "
        "E:2024-03-15",
        "R5 A:B-13 | B:Pain de campagne ⏎ au levain | C:3.2 | D:12 | "
        "E:2023-01-02"])
    assert text == want, "\n" + text


def test_csv_any_encoding_and_delimiter():
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, 'clients.csv')
    data = 'Nom;Ville;Téléphone\r\nHôtel du Lac;Genève;+41 22 123 45 67\r\n'
    with open(path, 'wb') as f:
        f.write(data.encode('cp1252'))
    sheet = sheets.load(path)[0]
    assert sheet.name == 'clients'
    assert sheet.rows == [['Nom', 'Ville', 'Téléphone'],
                          ['Hôtel du Lac', 'Genève', '+41 22 123 45 67']]


def test_long_sheets_show_head_and_tail():
    rows = [['Nom', 'Prix']] + [['Article %d' % i, i] for i in range(1, 60)]
    text = sheets.preview(sheets.Sheet('Liste', rows), ['products'])
    lines = text.splitlines()
    shown = [l for l in lines if l.startswith('R')]
    assert len(shown) == sheets.HEAD + sheets.TAIL
    assert '... 40 rows not shown ...' in lines
    assert shown[-1] == 'R60 A:Article 59 | B:59'
    assert lines[1] == 'LOCALE unknown'
    long_cell = sheets.show('x' * 50)
    assert len(long_cell) == sheets.CELL_CHARS and long_cell.endswith('…')


def test_values_line_shows_every_status_word():
    rows = [['N°', 'Statut']] + [['F-%d' % i, 'Payée'] for i in range(30)]
    rows.append(['F-99', 'Annulée'])          # only in a hidden row
    text = sheets.preview(sheets.Sheet('Factures', rows), ['invoice_ledger'])
    assert "VALUES B:Statut | Payée | Annulée" in text.splitlines()
    assert 'F-99' in text                     # last rows are shown too
    assert not any(l.startswith('VALUES A') for l in text.splitlines())


def test_csv_legacy_code_pages_follow_the_locale():
    folder = tempfile.mkdtemp()
    for locale, text, codec in [('ru-RU', 'Товар;Цена\r\nХлеб;45\r\n',
                                 'cp1251'),
                                ('ja-JP', '商品名,価格\r\nパン,300\r\n',
                                 'cp932')]:
        path = os.path.join(folder, 'list-%s.csv' % locale)
        with open(path, 'wb') as f:
            f.write(text.encode(codec))
        sheet = sheets.load(path, locale)[0]
        assert sheet.rows[1][0] in ('Хлеб', 'パン'), sheet.rows


def test_compact_removes_empty_columns():
    rows = [['Nom'] + [None] * 30 + ['Prix'],
            ['Pain'] + [None] * 30 + [1.3]]
    small, letters = sheets.compact(sheets.Sheet('Export', rows))
    assert small.rows == [['Nom', 'Prix'], ['Pain', 1.3]]
    assert letters == ['A', 'AF']
