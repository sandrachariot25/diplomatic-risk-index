"""Figures for the preprint (Russian and English versions) -> docs/preprint/figures/.

    python scripts/preprint_figures.py

Fig. 1  GDELT conflict share, Korea-Japan, monthly 2015-2026, with the 14 flare-ups coloured by expert cause type.
Fig. 2  Share of flare-ups preceded (1-3 months) by an elevated layer, vs. the ~25% expected by chance.
Fig. 3  Triggers in the onset month (or the month before): share of flare-ups vs. share of all months.
Static light-mode figures for print; every figure has a numeric table in the text (table-view twin).
Palette: reference categorical slots 1-3 (validated all-pairs, light), neutral grey for remaining classes.
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
from datetime import date  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / 'docs' / 'preprint' / 'figures'
INK, INK2, MUTED, GRID, AXIS, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'
TYPE_STYLE = {  # expert cause type -> (colour, RU label, EN label)
    'суды и история': (S1, 'Суды и история', 'Courts & history'),
    'наследие и символы': (S2, 'Наследие и символы', 'Heritage & symbols'),
    'экономика и рынки': (S3, 'Экономика и рынки', 'Economy & markets'),
    'other': (MUTED, 'Другое / неясно', 'Other / unclear'),
}
T = {
    'ru': dict(f1_title='Доля конфликтных событий Корея–Япония (GDELT), по месяцам',
               f1_y='Доля конфликтных событий', f1_note='Точки — 14 обострений; цвет — тип глубинной причины (экспертная разметка)',
               f2_title='Был ли слой выше нормы за 1–3 месяца до обострения',
               f2_x='Доля обострений, %', f2_chance='Ожидаемо случайно ≈ 25%',
               f3_title='Повод в месяце обострения или за месяц до',
               f3_y='%', f3_ep='Обострения (14)', f3_all='Все месяцы', source='Источник: расчёты автора; GDELT 1.0, Comtrade, ОЭСР, стенограммы парламентов РК и Японии'),
    'en': dict(f1_title='Share of conflictual Korea–Japan events (GDELT), monthly',
               f1_y='Conflict share', f1_note='Dots: 14 flare-ups; colour: deep-cause type (expert coding)',
               f2_title='Was the layer above its norm 1–3 months before a flare-up?',
               f2_x='Share of flare-ups, %', f2_chance='Expected by chance ≈ 25%',
               f3_title='Trigger in the onset month or the month before',
               f3_y='%', f3_ep='Flare-ups (14)', f3_all='All months', source='Source: author’s calculations; GDELT 1.0, Comtrade, OECD, ROK and Japan parliamentary records'),
}
LAYERS = {  # column in dri_v2_episodes.json -> (RU, EN)
    'x_chn_hostile': ('Враждебность Китая', 'China hostility'),
    'econ_balance_z12': ('Торговый баланс (откл.)', 'Trade balance (dev.)'),
    'kr_log_conf': ('Жёсткая риторика, парламент РК', 'Hard rhetoric, ROK parliament'),
    'riv_chips_agg': ('Соперничество: чипы', 'Rivalry: chips'),
    'm2_kr_memory_yoy': ('Бум корейской памяти', 'Korean memory boom'),
    'm2_kr_seafood_drop': ('Спад импорта японских морепродуктов в РК', 'Fall in ROK seafood imports from Japan'),
    'jp_r3': ('Жёсткая риторика, парламент Японии', 'Hard rhetoric, Japan parliament'),
    'a_kr_low': ('Низкий рейтинг президента РК', 'Low ROK presidential approval'),
    'material_pressure': ('Материальное давление (сводное)', 'Material pressure (composite)'),
    'm2_jp_slow': ('Спад промышленности Японии', 'Japanese industrial slowdown'),
    'a_jp_fall3': ('Падение рейтинга кабинета Японии', 'Falling Japan cabinet approval'),
    'x_prk_hostile': ('Враждебность КНДР', 'DPRK hostility'),
}


def style(ax):
    ax.set_facecolor(SURF)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig1(lang, t):
    g = list(csv.DictReader((DATA / 'gdelt_kor_jpn_monthly.csv').open(encoding='utf-8')))
    x = [date(int(r['month'][:4]), int(r['month'][5:]), 15) for r in g]
    y = [float(r['conflict_share']) for r in g]
    eps = json.loads((DATA / 'dri_v2_episode_causes_final.json').read_text(encoding='utf-8'))['episodes']
    level = {r['month']: float(r['conflict_share']) for r in g}
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=200, facecolor=SURF)
    style(ax)
    ax.grid(axis='x', visible=False)
    ax.plot(x, y, color=INK2, linewidth=1.4, zorder=2)
    used = set()
    for e in eps:
        key = e['final_type'] if e['final_type'] in TYPE_STYLE else 'other'
        col, ru, en = TYPE_STYLE[key]
        m = e['month']
        ax.scatter([date(int(m[:4]), int(m[5:]), 15)], [level[m]], s=46, color=col, edgecolor=SURF, linewidth=2,
                   zorder=3, label=(ru if lang == 'ru' else en) if key not in used else None)
        used.add(key)
        ax.annotate(m[2:].replace('-', '.'), (date(int(m[:4]), int(m[5:]), 15), level[m]), textcoords='offset points',
                    xytext=(0, 9), ha='center', fontsize=7, color=INK2, zorder=4,
                    bbox=dict(boxstyle='round,pad=0.15', fc=SURF, ec='none'))
    ax.set_ylabel(t['f1_y'], color=INK2, fontsize=9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.set_xlim(date(2014, 12, 1), date(2026, 12, 31))
    ax.set_ylim(0, max(y) * 1.12)
    order = ['суды и история', 'наследие и символы', 'экономика и рынки', 'other']
    h, lab = ax.get_legend_handles_labels()
    names = {TYPE_STYLE[k][1 if lang == 'ru' else 2]: k for k in order}
    pairs = sorted(zip(h, lab), key=lambda p: order.index(names[p[1]]))
    ax.legend([p[0] for p in pairs], [p[1] for p in pairs], frameon=False, fontsize=8, loc='upper right', ncol=2,
              labelcolor=INK)
    ax.set_title(t['f1_title'], loc='left', fontsize=11, color=INK, pad=10)
    fig.text(0.01, 0.01, t['f1_note'] + '. ' + t['source'], fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / f'fig1_gdelt_episodes_{lang}.png', facecolor=SURF)
    plt.close(fig)


def fig2(lang, t):
    feats = {f['column']: f for f in json.loads((DATA / 'dri_v2_episodes.json').read_text(encoding='utf-8'))['features']}
    items = []
    for col, (ru, en) in LAYERS.items():
        f = feats.get(col)
        if f:
            a = f['pre_1-3']
            items.append((100 * a['elevated'] / a['of'], ru if lang == 'ru' else en, a['elevated'], a['of'], a['p']))
    items.sort()
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200, facecolor=SURF)
    style(ax)
    ax.grid(axis='y', visible=False)
    ax.barh([i[1] for i in items], [i[0] for i in items], color=S1, height=0.6, zorder=2)
    for k, i in enumerate(items):
        ax.text(max(i[0], 25) + 1.5, k, f'{i[2]}/{i[3]}', va='center', fontsize=8, color=INK2, zorder=4,
                bbox=dict(boxstyle='round,pad=0.15', fc=SURF, ec='none'))
    ax.axvline(25, color=INK2, linewidth=1, zorder=3)
    ax.set_ylim(-1.3, len(items) - 0.5)
    ax.text(25.8, -1.0, t['f2_chance'], fontsize=8, color=INK2, va='center')
    ax.set_xlim(0, 100)
    ax.set_xlabel(t['f2_x'], color=INK2, fontsize=9)
    ax.tick_params(axis='y', labelsize=8.5, labelcolor=INK)
    ax.set_title(t['f2_title'], loc='left', fontsize=11, color=INK, pad=10)
    fig.text(0.01, 0.01, t['source'], fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / f'fig2_layers_before_flareups_{lang}.png', facecolor=SURF)
    plt.close(fig)


def fig3(lang, t):
    h = json.loads((DATA / 'dri_v2_triggers.json').read_text(encoding='utf-8'))['hit_rates']
    names = {'court': ('Решения корейских судов', 'Korean court rulings'),
             'election': ('Выборы (РК, Япония)', 'Elections (ROK, Japan)'),
             'recurring': ('Ежегодные даты', 'Annual dates')}
    keys = ['court', 'election', 'recurring']
    ep = [100 * h[k]['episodes_with_trigger'] / h[k]['of'] for k in keys]
    al = [100 * h[k]['share_all_months'] for k in keys]
    fig, ax = plt.subplots(figsize=(7.5, 4), dpi=200, facecolor=SURF)
    style(ax)
    ax.grid(axis='x', visible=False)
    xs = range(len(keys))
    w = 0.36
    b1 = ax.bar([i - w / 2 - 0.01 for i in xs], ep, width=w, color=S1, label=t['f3_ep'], zorder=2)
    b2 = ax.bar([i + w / 2 + 0.01 for i in xs], al, width=w, color=S2, label=t['f3_all'], zorder=2)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f'{b.get_height():.0f}%', ha='center',
                    fontsize=8, color=INK2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([names[k][0 if lang == 'ru' else 1] for k in keys], fontsize=9, color=INK)
    ax.set_ylim(0, 100)
    ax.set_ylabel(t['f3_y'], color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc='upper left', labelcolor=INK)
    ax.set_title(t['f3_title'], loc='left', fontsize=11, color=INK, pad=10)
    fig.text(0.01, 0.01, t['source'], fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / f'fig3_triggers_{lang}.png', facecolor=SURF)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams['font.family'] = ['Segoe UI', 'DejaVu Sans']
    for lang, t in T.items():
        fig1(lang, t)
        fig2(lang, t)
        fig3(lang, t)
    print('figures ->', OUT, sorted(p.name for p in OUT.glob('*.png')))


if __name__ == '__main__':
    main()
