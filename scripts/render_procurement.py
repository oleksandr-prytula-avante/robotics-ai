"""Render purchasing cards and budgets from procurement.json (no network access)."""
import argparse
import html
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def bi(ru, en):
    return {'ru': ru, 'en': en}

def span(value):
    if not value:
        return ''
    return ''.join(f'<span lang="{lang}">{html.escape(value[lang], quote=True)}</span>' for lang in ('ru', 'en'))

def money(value, currency):
    number = format(Decimal(str(value)), ',.2f').rstrip('0').rstrip('.').replace(',', ' ')
    return number + ' ' + currency

def totals(components):
    sums = {}
    for component in components:
        if component.get('reused_from') or component.get('included_in'):
            continue
        if component.get('unit_price') is None:
            continue
        currency = component['currency']
        sums[currency] = sums.get(currency, Decimal('0')) + Decimal(str(component['unit_price'])) * Decimal(str(component['quantity']))
    return {key: float(value.quantize(Decimal('0.01'))) for key, value in sorted(sums.items())}

def total_text(amounts):
    return ' + '.join(money(value, currency) for currency, value in amounts.items())

def price(item):
    if item.get('planning_allowance'):
        allowance = item['planning_allowance']
        amount = money(allowance['min'], allowance['currency']) + '–' + money(allowance['max'], allowance['currency'])
        return amount + ' · ' + span(bi('ориентир', 'planning allowance'))
    if item.get('market'):
        amounts = item['market']['totals']
        if amounts:
            return total_text(amounts)
        return span(bi('Уже учтено в других строках', 'Already budgeted in other rows'))
    if item['price'] is None:
        return span(bi('Стоимость уточняется', 'Cost pending confirmation'))
    return money(item['price'], item['currency'])

def link(url, label):
    return f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer">{label}</a>'

def component_table(components):
    out = '<div class="table-wrap"><table class="component-table"><thead><tr>'
    for heading in [bi('Товар / магазин','Product / seller'),bi('Кол-во','Qty'),bi('За единицу','Unit price'),bi('Сумма','Line total')]:
        out += '<th>' + span(heading) + '</th>'
    out += '</tr></thead><tbody>'
    for c in components:
        reused = c.get('reused_from') or c.get('included_in')
        if reused:
            destination = '#item-' + reused
            description = link(destination, span(c['name']))
            amount = span(bi('Учтено выше', 'Already counted'))
            unit_amount = '—'
        else:
            description = link(c['url'], span(c['name']))
            description += '<br><small>' + html.escape(c['seller']) + '</small>'
            unit_amount = money(c['unit_price'], c['currency'])
            amount = money(Decimal(str(c['unit_price'])) * Decimal(str(c['quantity'])), c['currency'])
        unit = c.get('unit', '')
        units = {'pcs': bi('шт.', 'pcs'), 'piece': bi('шт.', 'pcs'), 'pack': bi('уп.', 'pack'), 'set': bi('компл.', 'set'), 'kit': bi('компл.', 'kit'), '2-pack': bi('уп. по 2 шт.', '2-pack'), 'm': bi('м', 'm'), 'page': bi('стр.', 'page')}
        unit_label = span(units[unit]) if unit in units else html.escape(unit)
        quantity = span(bi('По этапу', 'By stage')) if reused else html.escape(str(c['quantity'])) + ' ' + unit_label
        out += '<tr><td>' + description + '</td><td>' + quantity + '</td><td>' + unit_amount + '</td><td>' + amount + '</td></tr>'
    return out + '</tbody></table></div>'

def market_details(market):
    out = '<div class="market-bom"><p><strong>' + span(bi('Состав и прямые ссылки','Components and direct purchase links')) + '</strong></p>'
    out += '<p class="small">' + span(market['scope']) + '</p>'
    out += component_table(market['components'])
    if market.get('notes'):
        out += '<p>' + span(market['notes']) + '</p>'
    if market.get('alternatives'):
        out += '<details><summary>' + span(bi('Альтернативы — не прибавляются к основной сумме','Alternatives — excluded from the main total')) + '</summary><div>'
        for alternative in market['alternatives']:
            if alternative.get('components'):
                out += '<p>' + span(alternative.get('name') or alternative.get('title') or bi('Другой вариант','Alternative')) + '</p>'
                out += component_table(alternative['components'])
                out += '<p>' + span(alternative.get('notes') or alternative.get('scope')) + '</p>'
            else:
                out += component_table([alternative])
        out += '</div></details>'
    out += '<details><summary>' + span(bi('Наличие, доставка и проверка цен','Availability, delivery and price evidence')) + '</summary><div>'
    evidence_components = list(market['components'])
    for alternative in market.get('alternatives', []):
        evidence_components.extend(alternative.get('components', [alternative]))
    seen = set()
    for c in evidence_components:
        if c.get('reused_from') or c.get('included_in'):
            continue
        if c['url'] in seen:
            continue
        seen.add(c['url'])
        out += '<p><strong>' + span(c['name']) + '</strong><br>'
        out += span(c.get('availability')) + ' ' + span(c.get('shipping_to_ukraine'))
        out += '<br><small>' + html.escape(c['checked_on']) + ' · ' + span(c.get('evidence_note')) + '</small>'
        for n, url in enumerate(c.get('sources', []), 1):
            if url != c['url']:
                out += ' ' + link(url, span(bi(f'Источник {n}', f'Source {n}')))
        out += '</p>'
    return out + '</div></details></div>'

def card(item):
    researched = bool(item.get('market'))
    out = '<article class="purchase-card anchor' + (' researched' if researched else '') + '" id="item-' + item['id'] + '">'
    out += '<div class="purchase-head"><span class="tag">' + span(item['classification_label']) + '</span><strong>' + price(item) + '</strong></div>'
    if item.get('planning_allowance'):
        label = bi('Отдельный приблизительный резерв; не проверенная цена продавца и не часть обязательного бюджета.', 'Separate rough allowance; not a checked supplier quote or part of the required budget.')
    else:
        label = bi('Стоимость указанного состава; доставка отдельно.','Cost of the listed components; shipping excluded.') if researched else bi('Цена за единицу или указанный комплект.','Price per unit or stated bundle.')
    out += '<p class="small">' + span(label) + '</p><h3>' + span(item['title']) + '</h3>'
    for key, css in [('quantity_text',''),('status_label','small'),('timing','small'),('compatibility',''),('notes','small')]:
        if item.get(key) and any(item[key].values()):
            out += '<p' + (' class="'+css+'"' if css else '') + '>' + span(item[key]) + '</p>'
    if researched:
        out += market_details(item['market'])
    elif not item.get('planning_allowance'):
        out += '<p class="small">' + span(bi('Дата проверки цены: ','Price checked: ')) + item['observed_on'] + '</p>'
    out += '<div class="purchase-links">'
    if item.get('url') and not researched:
        out += link(item['url'], html.escape(item['seller'] or 'Product')) + ' · '
    if item.get('project_link'):
        out += link(item['project_link'], span(bi('Факультативный PCB-проект хвоста', 'Optional tail PCB project'))) + ' '
    for n, url in enumerate(item.get('sources', []), 1):
        out += link(url, span(bi(f'Технический источник {n}',f'Technical source {n}'))) + ' '
    return out + '</div></article>'

def first_basket(data):
    index = {item['id']: item for item in data['items']}
    out = '<section id="first-basket"><h2>' + span(bi('Первая закупка: к электронике M04','First purchase: for M04 electronics')) + '</h2>'
    out += '<p>' + span(bi('Подготовить к 20 ноября 2026. Количество «1» у составной строки означает весь комплект из её карточки. Имеющиеся инструменты повторно покупать не нужно.','Prepare before 20 November 2026. Quantity “1” for a bundle means all components in its card. Reuse suitable tools already owned.')) + '</p>'
    out += '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+span(v)+'</th>' for v in [bi('Позиция','Item'),bi('Кол-во','Quantity'),bi('Сумма','Cost')]) + '</tr></thead><tbody>'
    for row in data['first_basket']:
        item = index[row['id']]
        amounts = {currency: value * row['quantity'] for currency, value in (item.get('market', {}).get('totals') or {item['currency']: item['price']}).items()}
        cost = total_text(amounts)
        out += '<tr><td>' + link('#item-'+item['id'],span(item['title'])) + '</td><td>' + str(row['quantity']) + '</td><td>' + cost + '</td></tr>'
    out += '</tbody></table></div><div class="note">'
    full = money(data['first_basket_subtotal_uah'],'UAH')
    essential = money(data['first_basket_without_workplace_uah'],'UAH')
    out += span(bi(f'Указанные комплекты: {full}. Без условной покупки стола и светильника: {essential}. Доставка не включена. У каждой составной строки ниже есть перечень товаров, количества и цены; повторно используемые материалы не прибавляются второй раз.',f'Listed bundles: {full}. Without the conditional desk and lamp purchase: {essential}. Shipping excluded. Each bundle below has product links, quantities and prices; reused materials are not charged twice.'))
    return out + '</div></section>'

def subsystem_budget(data):
    index = {item['id']: item for item in data['items']}
    out = '<section id="budget"><h2>' + span(bi('Стоимость выбранных комплектующих по узлам', 'Selected subsystem costs')) + '</h2>'
    out += '<p>' + span(data['budget_note']) + '</p><div class="table-wrap"><table><thead><tr>'
    out += ''.join('<th>'+span(value)+'</th>' for value in [bi('Сценарий','Scenario'),bi('Цена выбранных позиций','Selected-item cost'),bi('Что не включено','Excluded')])
    out += '</tr></thead><tbody>'
    for scenario in data['budget_scenarios']:
        amounts = []
        for variant in scenario['variants']:
            total = sum(Decimal(str(index[row['id']]['price'])) * row['quantity'] for row in variant)
            assert all(index[row['id']]['currency'] == 'UAH' for row in variant)
            amounts.append(money(total, 'UAH'))
        out += '<tr><td>' + span(scenario['name']) + '</td><td>' + ' / '.join(amounts) + '</td><td>' + span(scenario['excluded']) + '</td></tr>'
    return out + '</tbody></table></div></section>'

def render(data, source):
    for item in data['items']:
        pattern = r'<article\b[^>]*\bid="item-' + re.escape(item['id']) + r'".*?</article>'
        source, count = re.subn(pattern, lambda m: card(item), source, count=1, flags=re.S)
        assert count == 1, item['id']
    source = re.sub(r'<section id="first-basket">.*?</section>', lambda m: first_basket(data), source, count=1, flags=re.S)
    source = re.sub(r'<section id="budget">.*?</section>', lambda m: subsystem_budget(data), source, count=1, flags=re.S)
    out = '<section id="dependencies"><h2>' + span(bi('Что ещё нужно подготовить вместе с товаром','Dependencies to prepare alongside each product')) + '</h2>'
    for note in data['dependency_notes']:
        out += '<div class="panel"><h3>' + span(note['title']) + '</h3><p>' + span(note['detail']) + '</p>'
        for url in note.get('sources', []):
            out += link(url, span(bi('Технический источник','Technical source'))) + ' '
        out += '</div>'
    source = re.sub(r'<section id="dependencies">.*?</section>', lambda m: out+'</section>', source, count=1, flags=re.S)
    return source

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'procurement.json').read_text())
    path = ROOT / 'procurement.html'
    current = path.read_text()
    output = render(data, current)
    if args.check:
        if output != current:
            raise SystemExit('procurement.html is out of date; run python3 scripts/render_procurement.py')
        print('Procurement HTML matches JSON.')
    else:
        path.write_text(output)
