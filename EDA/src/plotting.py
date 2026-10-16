"""Построение графиков EDA. Все рисунки сохраняются в EDA/figures."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from . import catalog, config, loaders

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
    }
)

PALETTE = ["#2E5EAA", "#E4572E", "#17BEBB", "#FFC914", "#76B041", "#8E6C88", "#5C80BC"]


def _thousands(x, _):
    return f"{int(x):,}".replace(",", " ")


def _fmt_axis(ax):
    ax.xaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))


def _save(fig, name: str):
    path = config.FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  figure -> {path.name}")


# --------------------------------------------------------------------------- #
# 01. Размеры источников
def fig_sizes():
    s = loaders.load_json("traffic_summary.json")
    c = loaders.load_json("cards_summary.json")
    cat = loaders.load_json("catalog_summary.json")
    labels = ["Карточки\n(sku_desc)", "Офферы каталога\n(skus.pkl)", "Клики\n(query_clicks)"]
    vals = [c["n_rows"], cat["n_offers"], s["n_rows"]]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, vals, color=PALETTE[:3])
    ax.set_yscale("log")
    ax.set_ylabel("Число строк (лог. шкала)")
    ax.set_title("Размеры источников данных")
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{v:,}".replace(",", " "),
            ha="center",
            va="bottom",
            fontsize=10,
        )
    _save(fig, "01_dataset_sizes.png")


# 02. Пересечения источников
def fig_overlap():
    ov = loaders.load_json("coverage_summary.json")["overlap"]
    regs = [
        ("только карточки", ov["cards_only"]),
        ("только офферы", ov["offers_only"]),
        ("только клики", ov["clicks_only"]),
        ("офферы∩клики", ov["offers_clicks"] - ov["all_three"]),
        ("карточки∩клики", ov["cards_clicks"] - ov["all_three"]),
        ("офферы∩карточки", ov["offers_cards"] - ov["all_three"]),
        ("во всех трёх", ov["all_three"]),
    ]
    regs.sort(key=lambda x: x[1])
    labels = [r[0] for r in regs]
    vals = [r[1] for r in regs]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = [PALETTE[1] if "всех трёх" in l else PALETTE[0] for l in labels]
    bars = ax.barh(labels, vals, color=colors)
    ax.set_xlabel("SKU, шт.")
    ax.set_title("Пересечение множеств SKU между тремя источниками")
    for b, v in zip(bars, vals):
        ax.text(
            v, b.get_y() + b.get_height() / 2, f" {v:,}".replace(",", " "), va="center", fontsize=9
        )
    _fmt_axis(ax)
    _save(fig, "02_overlap.png")


# 03. Трафик по категориям
def fig_traffic_categories():
    df = pd.read_csv(config.RESULTS_DIR / "top_categories_traffic.csv").head(20)
    df = df.dropna(subset=["category_name"]).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 7))
    ax.barh(df.category_name, df.clicks, color=PALETTE[2])
    ax.set_xlabel("Клики, шт.")
    ax.set_title("Топ-20 категорий по кликовому трафику")
    for y, v in zip(range(len(df)), df.clicks):
        ax.text(v, y, f" {v:,}".replace(",", " "), va="center", fontsize=8)
    _fmt_axis(ax)
    _save(fig, "03_category_traffic.png")


# 04. Распределение числа атрибутов на оффер
def fig_params_per_offer():
    off = pd.read_parquet(config.CACHE_DIR / "offers_flat.parquet")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(off.n_params, bins=60, color=PALETTE[0])
    ax.set_xlabel("Число параметров у оффера")
    ax.set_ylabel("Число офферов")
    ax.set_title("Сколько атрибутов приходит с оффером")
    ax.axvline(
        off.n_params.median(),
        color=PALETTE[1],
        ls="--",
        label=f"медиана {off.n_params.median():.0f}",
    )
    ax.legend()
    _fmt_axis(ax)
    _save(fig, "04_params_per_offer.png")


# 05. Длинный хвост имён параметров
def fig_param_longtail():
    ps = pd.read_parquet(config.CACHE_DIR / "param_stats.parquet")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].hist(np.log10(ps.n.clip(lower=1)), bins=40, color=PALETTE[0])
    axes[0].set_xlabel("log10(число вхождений параметра)")
    axes[0].set_ylabel("Число имён параметров")
    axes[0].set_title("Частотный спектр имён параметров")
    sorted_n = np.sort(ps.n.values)[::-1]
    axes[1].plot(np.arange(1, len(sorted_n) + 1), sorted_n, color=PALETTE[1])
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Ранг параметра")
    axes[1].set_ylabel("Вхождений")
    axes[1].set_title("Длинный хвост: ранг-размер")
    _save(fig, "05_param_longtail.png")


# 06. Топ параметров
def fig_top_params():
    ps = pd.read_parquet(config.CACHE_DIR / "param_stats.parquet").head(30).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 8))
    ax.barh(ps.param, ps.n, color=PALETTE[0])
    ax.set_xlabel("Число вхождений")
    ax.set_title("Топ-30 имён параметров каталога")
    _fmt_axis(ax)
    _save(fig, "06_top_params.png")


# 07. Единицы измерения (@unit)
def fig_units():
    ps = pd.read_parquet(config.CACHE_DIR / "param_stats.parquet")
    units = ps[ps.top_unit != ""].top_unit.value_counts().head(25)
    fig, ax = plt.subplots(figsize=(8.5, 6))
    ax.barh(units.index[::-1], units.values[::-1], color=PALETTE[4])
    ax.set_xlabel("Число параметров с данной единицей")
    ax.set_title("Структурированные единицы измерения (@unit)")
    _fmt_axis(ax)
    _save(fig, "07_units.png")


# 08. Кардинальность vs частота
def fig_cardinality():
    ps = pd.read_parquet(config.CACHE_DIR / "param_stats.parquet")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sc = ax.scatter(ps.n, ps.n_vals.clip(lower=1), s=10, c=ps.num_share, cmap="viridis", alpha=0.6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Число вхождений параметра")
    ax.set_ylabel("Число уникальных значений")
    ax.set_title("Частота vs кардинальность (цвет = доля числовых)")
    fig.colorbar(sc, ax=ax, label="доля числовых значений")
    _save(fig, "08_param_cardinality.png")


# 09. Размер категорий
def fig_category_sizes():
    off = pd.read_parquet(config.CACHE_DIR / "offers_flat.parquet")
    cats = pd.read_parquet(config.CACHE_DIR / "categories.parquet")
    cnt = off.category_id.astype(str).value_counts()
    name = dict(zip(cats.category_id.astype(str), cats.category_name))
    top = cnt.head(25)[::-1]
    labels = [name.get(i, i) for i in top.index]
    fig, ax = plt.subplots(figsize=(8.5, 8))
    ax.barh(labels, top.values, color=PALETTE[5])
    ax.set_xlabel("Число офферов")
    ax.set_title("Топ-25 категорий по числу офферов")
    _fmt_axis(ax)
    _save(fig, "09_category_sizes.png")


# 10. Тепловая карта заполненности целевых атрибутов
# Коды атрибутов соответствуют доменной модели (openspec/specs/domain-model.md).
def _focus_fill_matrix():
    ca = pd.read_parquet(config.CACHE_DIR / "cat_attr.parquet")
    off = pd.read_parquet(config.CACHE_DIR / "offers_flat.parquet")
    cats = pd.read_parquet(config.CACHE_DIR / "categories.parquet")
    focus_ids = catalog._focus_category_ids(cats, off)
    alias = {}
    for code, meta in config.TARGET_ATTRIBUTES.items():
        for a in meta["aliases"]:
            alias[a.lower()] = code
    cols = [
        "brand",
        "model",
        "color",
        "material",
        "storage",
        "drive",
        "ram",
        "diagonal",
        "battery_capacity",
        "processor",
        "os",
        "resolution",
        "refresh_rate",
        "weight",
        "country",
    ]
    order = [c for c in dict.fromkeys(config.FOCUS_CATEGORIES) if c in focus_ids]
    ca = ca.copy()
    ca["code"] = ca.param.str.lower().map(alias)
    m = np.full((len(order), len(cols)), np.nan)
    for i, cname in enumerate(order):
        cid = str(focus_ids[cname])
        v = off[off.category_id.astype(str) == cid]
        if not v.empty:
            m[i, 0] = v.vendor.notna().mean()
            m[i, 1] = v.model.notna().mean()
        sub = ca[ca.category_id.astype(str) == cid]
        for j, code in enumerate(cols[2:], start=2):
            r = sub[sub.code == code]
            if not r.empty:
                m[i, j] = r.fill_rate.max()
    return order, cols, m


def fig_focus_heatmap():
    order, codes, m = _focus_fill_matrix()
    cols = [config.TARGET_ATTRIBUTES[c]["label"] for c in codes]
    present = m[~np.isnan(m)]
    vmin = np.floor(min(0.75, float(present.min())) / 0.05) * 0.05 if present.size else 0.0
    cmap = matplotlib.colormaps["RdYlGn"].copy()
    cmap.set_bad("#D9D9D9")
    fig, ax = plt.subplots(figsize=(12, 6.2))
    im = ax.imshow(np.ma.masked_invalid(m), cmap=cmap, vmin=vmin, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(cols)), cols, rotation=40, ha="right")
    ax.set_yticks(range(len(order)), order)
    ax.set_title("Заполненность целевых атрибутов по категориям (доля офферов)")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if np.isnan(m[i, j]):
                ax.text(j, i, "—", ha="center", va="center", fontsize=8, color="#888888")
            else:
                ax.text(j, i, f"{m[i, j]:.0%}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label=f"доля заполненных (шкала от {vmin:.0%})")
    ax.set_xlabel(
        "«—» (серый) — атрибут отсутствует в схеме категории", fontsize=9, color="#666666"
    )
    _save(fig, "10_focus_heatmap.png")


# 11-12. Атрибуты смартфонов / ноутбуков
def _fig_category_attrs(category: str, fname: str, drop_search=True):
    focus = pd.read_parquet(config.CACHE_DIR / "focus_attrs.parquet")
    sub = focus[focus.category_name == category].copy()
    sub = sub[~sub.param.isin(["brand (vendor)", "model"])]
    sub = sub.sort_values("fill_rate", ascending=False).head(22).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 8))
    ax.barh(sub.param, sub.fill_rate, color=PALETTE[0])
    ax.set_xlabel("Доля офферов с заполненным атрибутом")
    ax.set_xlim(0, 1)
    ax.set_title(f"Атрибуты категории «{category}»")
    for y, (fr, nd) in enumerate(zip(sub.fill_rate, sub.n_distinct)):
        ax.text(fr + 0.01, y, f"{fr:.0%} · {nd} знач.", va="center", fontsize=8)
    _save(fig, fname)


def fig_smartphone_attrs():
    _fig_category_attrs("Смартфоны", "11_smartphone_attrs.png")


def fig_laptop_attrs():
    _fig_category_attrs("Ноутбуки", "12_laptop_attrs.png")


# 13. Длины карточек
def fig_card_lengths():
    df = pd.read_parquet(config.CACHE_DIR / "cards_lengths.parquet")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].hist(df.title_len.clip(upper=200), bins=60, color=PALETTE[0])
    axes[0].set_title("Длина заголовка")
    axes[0].set_xlabel("Символов")
    axes[0].set_ylabel("Карточек")
    axes[1].hist(df.desc_len.clip(upper=5000), bins=60, color=PALETTE[1])
    axes[1].set_title("Длина описания")
    axes[1].set_xlabel("Символов")
    _fmt_axis(axes[0])
    _fmt_axis(axes[1])
    _save(fig, "13_card_lengths.png")


# 14. Разметка и маркеры в описаниях
def fig_card_markup():
    c = loaders.load_json("cards_summary.json")
    d = c["columns"]["description"]
    t = c["columns"]["title"]
    items = [
        ("HTML-теги (опис.)", d["has_html_tag_share"]),
        ("<br> (опис.)", d["has_br_share"]),
        ("переносы \\n (опис.)", d["has_newline_share"]),
        ("HTML-сущности (опис.)", d["has_entity_share"]),
        ("URL (опис.)", d["has_url_share"]),
        ("цифры (опис.)", d["has_digit_share"]),
        ("HTML-теги (title)", t["has_html_tag_share"]),
    ]
    items.sort(key=lambda x: x[1])
    labels = [i[0] for i in items]
    vals = [i[1] for i in items]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.barh(labels, vals, color=PALETTE[3])
    ax.set_xlabel("Доля карточек")
    ax.set_title("Разметка и служебные элементы в тексте карточек")
    for y, v in enumerate(vals):
        ax.text(v + 0.005, y, f"{v:.1%}", va="center", fontsize=9)
    ax.set_xlim(0, max(vals) * 1.2)
    _save(fig, "14_card_markup.png")


# 15. Язык заголовков
def fig_title_lang():
    c = loaders.load_json("cards_summary.json")
    mix = c["title_lang_mix"]
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = list(mix.keys())
    vals = list(mix.values())
    ax.bar(labels, vals, color=[PALETTE[0], PALETTE[4], PALETTE[1]])
    ax.set_ylabel("Карточек")
    ax.set_title("Языковой состав заголовков")
    for x, v in zip(range(len(vals)), vals):
        ax.text(x, v, f"{v:,}".replace(",", " "), ha="center", va="bottom", fontsize=9)
    _fmt_axis(ax)
    _save(fig, "15_title_lang.png")


# 16. Заземление атрибутов в тексте
def fig_grounding():
    g = loaders.load_json("coverage_summary.json")["grounding"]
    fields = ["vendor", "model", "color"]
    title = [g[f]["title"] for f in fields]
    desc = [g[f]["desc"] for f in fields]
    anyv = [g[f]["any"] for f in fields]
    x = np.arange(len(fields))
    w = 0.26
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar(x - w, title, w, label="в заголовке", color=PALETTE[0])
    ax.bar(x, desc, w, label="в описании", color=PALETTE[1])
    ax.bar(x + w, anyv, w, label="хоть где-то", color=PALETTE[4])
    ax.set_xticks(x, ["Бренд", "Модель", "Цвет"])
    ax.set_ylabel("Доля офферов с найденным значением")
    ax.set_title("Заземление эталонных атрибутов в тексте карточки")
    ax.legend()
    _save(fig, "16_grounding.png")


# 17. Форматы памяти и диагонали
def fig_value_formats():
    st = loaders.load_json("storage_norm.json")
    sc = loaders.load_json("diagonal_norm.json")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, d, title in [
        (axes[0], st, "Форматы значений «память»"),
        (axes[1], sc, "Форматы значений «диагональ»"),
    ]:
        fc = d["format_counts"]
        fc = dict(sorted(fc.items(), key=lambda x: x[1]))
        ax.barh(list(fc.keys()), list(fc.values()), color=PALETTE[2])
        ax.set_title(title)
        ax.set_xlabel("Вхождений")
        _fmt_axis(ax)
    _save(fig, "17_value_formats.png")


# 18. «Грязь» цвета
def fig_color_messiness():
    d = loaders.load_json("color_norm.json")
    top = d["top_values"][:18]
    labels = [t[0] for t in top][::-1]
    vals = [t[1] for t in top][::-1]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].barh(labels, vals, color=PALETTE[0])
    axes[0].set_title("Топ значений цвета")
    axes[0].set_xlabel("Вхождений")
    _fmt_axis(axes[0])
    coll = d["collisions_sample"]
    keys = list(coll.keys())[:10]
    worst = sorted(keys, key=lambda k: -len(coll[k]))
    ex_labels = []
    ex_vals = []
    for k in worst:
        for variant, cnt in coll[k].items():
            ex_labels.append(f"{variant}")
            ex_vals.append(cnt)
    axes[1].barh(range(len(ex_vals)), ex_vals, color=PALETTE[1])
    axes[1].set_yticks(range(len(ex_vals)), ex_labels, fontsize=8)
    axes[1].set_title("Дубликаты после нормализации регистра/ё")
    axes[1].set_xlabel("Вхождений")
    _fmt_axis(axes[1])
    _save(fig, "18_color_messiness.png")


# 19. Цены
def fig_prices():
    s = loaders.load_json("traffic_summary.json")
    df = pd.read_parquet(config.CACHE_DIR / "price_sample.parquet")
    price = df.price[df.price > 0]
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.hist(np.log10(price), bins=80, color=PALETTE[0])
    ax.set_xlabel("log10(цена, ₽)")
    ax.set_ylabel("Наблюдений")
    ax.set_title("Распределение цен товаров в трафике")
    q = s["price_quantiles"]
    ax.axvline(
        np.log10(q["0.5"]),
        color=PALETTE[1],
        ls="--",
        label=f"медиана {q['0.5']:,.0f} ₽".replace(",", " "),
    )
    ax.legend()
    _fmt_axis(ax)
    _save(fig, "19_prices.png")


# 20. Позиция клика (CTR-распад)
def fig_position():
    s = loaders.load_json("traffic_summary.json")
    pos = s["position_counts_head"]
    ks = sorted(int(k) for k in pos)
    vs = [pos[str(k)] for k in ks]
    cum = np.cumsum(vs) / s["n_rows"]
    fig, ax1 = plt.subplots(figsize=(7.5, 4.4))
    ax1.bar(ks, vs, color=PALETTE[0])
    ax1.set_xlabel("Позиция в выдаче")
    ax1.set_ylabel("Кликов")
    ax1.set_title("Распределение кликов по позициям")
    _fmt_axis(ax1)
    _save(fig, "20_position.png")


# 21. Дубликаты и аномалии-карточки
def fig_dup_anomalies():
    c = loaders.load_json("cards_summary.json")
    n = c["n_rows"]
    items = [
        ("Дубликаты заголовков", c["dup_titles"] / n),
        ("Дубликаты описаний", c["dup_descriptions"] / n),
        ("Заголовок с цифрами", c["columns"]["title"]["has_digit_share"]),
    ]
    items.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.barh([i[0] for i in items], [i[1] for i in items], color=PALETTE[1])
    for y, v in enumerate([i[1] for i in items]):
        ax.text(v + 0.005, y, f"{v:.1%}", va="center", fontsize=9)
    ax.set_xlim(0, max(i[1] for i in items) * 1.25)
    ax.set_xlabel("Доля карточек")
    ax.set_title("Дубликаты и повторяющиеся шаблоны в карточках")
    _save(fig, "21_dup_anomalies.png")


def run():
    print("[figures] building ...")
    for fn in [
        fig_sizes,
        fig_overlap,
        fig_traffic_categories,
        fig_params_per_offer,
        fig_param_longtail,
        fig_top_params,
        fig_units,
        fig_cardinality,
        fig_category_sizes,
        fig_focus_heatmap,
        fig_smartphone_attrs,
        fig_laptop_attrs,
        fig_card_lengths,
        fig_card_markup,
        fig_title_lang,
        fig_grounding,
        fig_value_formats,
        fig_color_messiness,
        fig_prices,
        fig_position,
        fig_dup_anomalies,
    ]:
        fn()
    print("[figures] done")
