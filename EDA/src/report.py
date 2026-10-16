"""Сборка PDF-отчёта по результатам EDA (reportlab)."""

from __future__ import annotations

import datetime as dt
import os
from xml.sax.saxutils import escape

import matplotlib
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from . import config, loaders, plotting

# --------------------------------------------------------------------------- #
# Шрифты с поддержкой кириллицы (берём из matplotlib)
_MPL_FONTS = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_MPL_FONTS, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_MPL_FONTS, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Mono", os.path.join(_MPL_FONTS, "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")

CONTENT_W = A4[0] - 3.4 * cm  # ширина контента при отступах 1.7 см
ACCENT = colors.HexColor("#2E5EAA")
ACCENT2 = colors.HexColor("#E4572E")
LIGHT = colors.HexColor("#EEF2F8")

_styles = getSampleStyleSheet()


def _style(name, **kw):
    base = kw.pop("parent", _styles["BodyText"])
    kw.setdefault("fontName", "DejaVu")
    return ParagraphStyle(name, parent=base, **kw)


S = {
    "title": _style("title", fontName="DejaVu-Bold", fontSize=26, leading=30, textColor=ACCENT),
    "subtitle": _style("subtitle", fontSize=14, leading=18, textColor=colors.HexColor("#444444")),
    "h1": _style(
        "h1",
        fontName="DejaVu-Bold",
        fontSize=17,
        leading=22,
        textColor=ACCENT,
        spaceBefore=6,
        spaceAfter=8,
    ),
    "h2": _style(
        "h2",
        fontName="DejaVu-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1F3B66"),
        spaceBefore=10,
        spaceAfter=5,
    ),
    "body": _style("body", fontSize=10, leading=14.5, spaceAfter=6, alignment=4),
    "bullet": _style(
        "bullet", fontSize=10, leading=14.5, leftIndent=14, bulletIndent=4, spaceAfter=3
    ),
    "small": _style("small", fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")),
    "mono": _style("mono", fontName="DejaVu-Mono", fontSize=8.5, leading=11.5),
    "cap": _style(
        "cap",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#666666"),
        alignment=1,
        spaceBefore=2,
    ),
}


def ru(n, dec=0):
    if isinstance(n, float):
        s = f"{n:,.{dec}f}"
    else:
        s = f"{int(n):,}"
    return s.replace(",", " ").replace(".", ",")


def pct(x, dec=1):
    return f"{x * 100:.{dec}f}%".replace(".", ",")


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, style="bullet"):
    return [Paragraph(f"•&nbsp;&nbsp;{t}", S[style]) for t in items]


def img_flow(name, max_w=CONTENT_W, max_h=18 * cm):
    path = config.FIGURES_DIR / name
    ir = ImageReader(str(path))
    iw, ih = ir.getSize()
    w = max_w
    h = ih * w / iw
    if h > max_h:
        h = max_h
        w = iw * h / ih
    return Image(str(path), width=w, height=h)


def fig_block(name, caption, max_h=18 * cm):
    return [Spacer(1, 4), img_flow(name, max_h=max_h), P(caption, "cap"), Spacer(1, 6)]


def make_table(header, rows, col_widths=None, font_size=9):
    data = [[Paragraph(f"<b>{escape(str(h))}</b>", S["body"]) for h in header]]
    for r in rows:
        data.append([Paragraph(escape(str(c)), S["body"]) if isinstance(c, str) else c for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D9")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


# --------------------------------------------------------------------------- #
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(1.7 * cm, 1.0 * cm, "SpecFlow — EDA отчёт")
    canvas.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"стр. {doc.page}")
    canvas.restoreState()


class _Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(
            path,
            pagesize=A4,
            leftMargin=1.7 * cm,
            rightMargin=1.7 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
            title="SpecFlow EDA",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_footer)])


# --------------------------------------------------------------------------- #
def _load():
    return {
        "cards": loaders.load_json("cards_summary.json"),
        "catalog": loaders.load_json("catalog_summary.json"),
        "traffic": loaders.load_json("traffic_summary.json"),
        "coverage": loaders.load_json("coverage_summary.json"),
        "storage": loaders.load_json("storage_norm.json"),
        "diagonal": loaders.load_json("diagonal_norm.json"),
        "color": loaders.load_json("color_norm.json"),
    }


def _title_page(D):
    c, cat, t = D["cards"], D["catalog"], D["traffic"]
    story = [
        Spacer(1, 3.2 * cm),
        P("SpecFlow", "subtitle"),
        P("Разведочный анализ данных (EDA)", "title"),
        Spacer(1, 0.4 * cm),
        P(
            "Автоматическое извлечение характеристик товаров из текстовых карточек<br/>"
            "Кейс М.Видео — маркетплейс электроники",
            "subtitle",
        ),
        Spacer(1, 1.2 * cm),
        make_table(
            ["Источник", "Строк", "Сущность"],
            [
                ["sku_desc.parquet", ru(c["n_rows"]), "текстовые карточки (title, description)"],
                ["skus.pkl (YML)", ru(cat["n_offers"]), "офферы каталога + параметры-атрибуты"],
                ["query_clicks.parquet", ru(t["n_rows"]), "поисковые клики (трафик)"],
            ],
            col_widths=[5.5 * cm, 3.0 * cm, 8.0 * cm],
        ),
        Spacer(1, 1.0 * cm),
        P(
            f"Отчёт сгенерирован автоматически: {dt.date.today():%d.%m.%Y}. "
            "Все числа получены скриптами пакета <font face='DejaVu-Mono'>EDA/src</font> "
            "непосредственно из датасета.",
            "small",
        ),
        PageBreak(),
    ]
    return story


def _section_summary(D):
    c, cat, t, cov = D["cards"], D["catalog"], D["traffic"], D["coverage"]
    g = cov["grounding"]
    story = [P("1. Краткое резюме", "h1")]
    story += bullets(
        [
            f"Датасет состоит из трёх независимых срезов: <b>{ru(c['n_rows'])}</b> текстовых карточек, "
            f"<b>{ru(cat['n_offers'])}</b> офферов каталога с разметкой атрибутов и <b>{ru(t['n_rows'])}</b> строк кликового трафика.",
            f"Эталонные атрибуты есть только у офферов каталога: в среднем <b>{ru(cat['params_per_offer_mean'], 1)}</b> параметра на товар, "
            f"суммарно <b>{ru(cat['total_param_assignments'])}</b> присвоений по <b>{ru(cat['n_distinct_param_names'])}</b> уникальным именам (после слияния дублей <font face='DejaVu-Mono'>_search</font>).",
            f"Связность источников низкая: карточки и каталог пересекаются лишь по <b>{ru(cov['overlap']['offers_cards'])}</b> SKU, "
            f"во всех трёх сразу — <b>{ru(cov['overlap']['all_three'])}</b> SKU ({pct(cov['overlap']['all_three'] / cov['overlap']['n_offers'])} от каталога).",
            f"Бренд и модель отлично «заземляются» в тексте: у бренда значение найдено в заголовке в <b>{pct(g['vendor']['title'])}</b> случаев, "
            f"у модели — <b>{pct(g['model']['title'])}</b>. Цвет же в тексте почти не встречается (<b>{pct(g['color']['any'])}</b>) — его нельзя брать из текста без обращения к структурным полям.",
            f"Текст карточек «грязный»: <b>{pct(c['columns']['description']['has_html_tag_share'])}</b> описаний содержат HTML-теги, "
            f"<b>{pct(c['columns']['description']['has_br_share'])}</b> — <font face='DejaVu-Mono'>&lt;br&gt;</font>; "
            f"<b>{pct(c['dup_titles'] / c['n_rows'])}</b> заголовков — дубликаты.",
            f"Таксономия огромна и имеет длинный хвост: <b>{ru(cat['n_distinct_param_names'])}</b> имён атрибутов, "
            f"из них <b>{ru(cat['long_tail_params']['lt_100'])}</b> встречаются реже 100 раз. Офферов всего "
            f"<b>{ru(cat['n_offers'])}</b>, то есть на большинство атрибутов примеров крайне мало.",
            f"Структурированные поля каталога <b>уже нормализованы</b> (единицы в отдельном <font face='DejaVu-Mono'>@unit</font>, "
            f"значения — из ограниченных словарей), а вот входной текст — нет. Это подтверждает выбор гибридного пайплайна: "
            "правила/словари для ядра + ML/LLM для хвоста и свободного текста.",
        ]
    )
    story += [P("Ключевой вывод для задачи", "h2")]
    story += bullets(
        [
            "Строить канонический справочник атрибутов и значений нужно <b>из структурированных параметров каталога</b>, "
            "а текст карточки использовать как неструктурированный вход для извлечения.",
            "Категория товара в карточках sku_desc <b>отсутствует</b> — её придётся выводить из текста или тянуть из каталога по SKU.",
            "Значительная часть «атрибутов» в каталоге — служебные (продавец, гарантия, подборки, BI-поля) и маркетинговые. "
            "Их нужно отфильтровать, оставив реальные товарные характеристики.",
            "Низкое пересечение источников — риск: обучаться/валидироваться можно только на подмножестве "
            f"({ru(cov['overlap']['all_three'])} SKU с текстом и трафиком одновременно).",
        ]
    )
    story.append(PageBreak())
    return story


def _section_sources(D):
    c, cat, t = D["cards"], D["catalog"], D["traffic"]
    story = [P("2. Источники данных и схема", "h1")]
    story.append(P("2.1. Карточки товаров — sku_desc.parquet", "h2"))
    story.append(
        make_table(
            ["Поле", "Тип", "Описание", "Пропусков"],
            [
                ["sku_id", "int64", "идентификатор SKU", "0"],
                ["title", "str", "название карточки", "0"],
                ["description", "str", "полное описание (HTML)", "0"],
            ],
            col_widths=[3.0 * cm, 2.0 * cm, 8.5 * cm, 3.0 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            f"Объём: <b>{ru(c['n_rows'])}</b> строк, все SKU уникальны. Категории в файле нет.",
            "body",
        ),
        P("2.2. Каталог — skus.pkl (формат YML)", "h2"),
        make_table(
            ["Поле оффера", "Тип", "Описание", "Заполнено"],
            [
                ["@id", "str", "идентификатор оффера (≈ SKU)", "100%"],
                ["name", "str", "название товара", "100%"],
                ["vendor", "str", "бренд (эталон)", pct(cat["vendor_fill"])],
                ["model", "str", "модель (эталон, часто составная строка)", pct(cat["model_fill"])],
                ["categories.categoryId", "str", "идентификатор категории", "100%"],
                ["param[]", "list[dict]", "параметры: @name, @unit, #text", "100%"],
                ["@available", "bool", "в наличии", "100%"],
            ],
            col_widths=[4.2 * cm, 2.2 * cm, 7.3 * cm, 2.8 * cm],
        ),
        Spacer(1, 6),
        P(
            "Модель категорий: 6&nbsp;963 узла, дерево глубины до 3 уровней "
            f"({ru(cat['n_categories_used'])} категорий реально используются).",
            "body",
        ),
        P("2.3. Кликовый трафик — query_clicks.parquet", "h2"),
        make_table(
            ["Поле", "Тип", "Описание"],
            [
                ["sku_id", "uint64", "SKU, который показали/кликнули"],
                ["query_text", "str", "поисковый запрос"],
                ["sku_brand_name", "str", "бренд из выдачи"],
                ["sku_subject_id", "uint64", "id тематики (совпадает с категориями каталога)"],
                ["sku_seo_id", "uint64", "id SEO-группы"],
                ["sku_price", "float", "цена, ₽"],
                ["sku_position", "uint64", "позиция товара в выдаче"],
            ],
            col_widths=[3.5 * cm, 2.2 * cm, 11.3 * cm],
        ),
        Spacer(1, 6),
        P(
            f"Объём: <b>{ru(t['n_rows'])}</b> строк; <b>{ru(t['n_unique_sku'])}</b> уникальных SKU, "
            f"<b>{ru(t['n_unique_subject'])}</b> тематик, {ru(len(t['top_queries']))} показанных топ-запросов "
            "использованы в анализе.",
            "body",
        ),
        PageBreak(),
    ]
    return story


def _section_coverage(D):
    cov = D["coverage"]
    ov = cov["overlap"]
    g = cov["grounding"]
    story = [P("3. Покрытие и связывание источников", "h1")]
    story.append(
        P(
            "Три файла — это разные снимки каталога, а не строго согласованные таблицы. "
            "Пересечение по SKU показано ниже и является ограничением задачи.",
            "body",
        )
    )
    story += fig_block("02_overlap.png", "Рис. 1. Пересечение множеств SKU между источниками.")
    story.append(
        make_table(
            ["Регион", "SKU"],
            [
                ["Только карточки (нет в каталоге)", ru(ov["cards_only"])],
                ["Только офферы каталога (нет текста)", ru(ov["offers_only"])],
                ["Офферы ∩ карточки (текст + эталон)", ru(ov["offers_cards"])],
                ["Офферы ∩ клики", ru(ov["offers_clicks"])],
                ["Карточки ∩ клики", ru(ov["cards_clicks"])],
                ["Во всех трёх источниках", ru(ov["all_three"])],
            ],
            col_widths=[11.0 * cm, 5.0 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            f"Из <b>{ru(ov['n_cards'])}</b> карточек лишь <b>{ru(ov['offers_cards'])}</b> "
            f"({pct(ov['offers_cards'] / ov['n_cards'])}) имеют эталонную разметку атрибутов в каталоге. "
            f"Это и есть потенциальная обучающая/валидационная выборка. Ещё <b>{ru(ov['offers_only'])}</b> офферов "
            "каталога вообще не имеют текста — на них нельзя обучить извлечение, но можно использовать как словарь значений.",
            "body",
        ),
        P("3.1. Заземление эталонных атрибутов в тексте", "h2"),
    ]
    story += fig_block(
        "16_grounding.png",
        "Рис. 2. Доля офферов, где эталонное значение найдено в тексте карточки.",
    )
    story.append(
        make_table(
            ["Атрибут", "Найдено в заголовке", "Найдено в описании", "Хоть где-то"],
            [
                [
                    "Бренд (vendor)",
                    pct(g["vendor"]["title"]),
                    pct(g["vendor"]["desc"]),
                    pct(g["vendor"]["any"]),
                ],
                [
                    "Модель (model)",
                    pct(g["model"]["title"]),
                    pct(g["model"]["desc"]),
                    pct(g["model"]["any"]),
                ],
                ["Цвет", pct(g["color"]["title"]), pct(g["color"]["desc"]), pct(g["color"]["any"])],
            ],
            col_widths=[4.5 * cm, 4.0 * cm, 4.0 * cm, 3.5 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            "Бренд практически всегда присутствует в заголовке — это делает его самым надёжным атрибутом для правил. "
            "Модель тоже хорошо находится, но поле <font face='DejaVu-Mono'>model</font> в каталоге часто содержит "
            "не чистую модель, а длинную составную строку (цвет, память, парт-номер), поэтому его нужно нормализовать. "
            "Цвет в тексте почти не встречается: <b>его нельзя извлечь только из описания</b>, нужен словарь цветов и "
            "структурное поле. Также важно: бренд в каталоге в "
            f"{pct(cov['vendor_latin_share'])} случаев содержит латиницу, тогда как текст — преимущественно кириллица "
            "(транслитерации и разные написания).",
            "body",
        ),
        P("Примеры, где модель НЕ найдена в заголовке:", "small"),
    ]
    ex_rows = [
        [
            e["sku_id"],
            str(e["title"])[:60],
            str(e["vendor"]),
            str(e["model"])[:40],
        ]
        for e in cov["grounding_examples"][:5]
    ]
    story.append(
        make_table(
            ["sku_id", "title", "vendor", "model"],
            ex_rows,
            col_widths=[2.4 * cm, 6.6 * cm, 2.4 * cm, 4.6 * cm],
            font_size=8,
        )
    )
    story.append(PageBreak())
    return story


def _section_cards(D):
    c = D["cards"]
    tc, dc = c["columns"]["title"], c["columns"]["description"]
    story = [P("4. Анализ текстовых карточек", "h1")]
    story += fig_block("13_card_lengths.png", "Рис. 3. Распределение длин заголовков и описаний.")
    story.append(
        make_table(
            ["Метрика", "Заголовок", "Описание"],
            [
                ["Средняя длина", ru(tc["len_mean"], 1), ru(dc["len_mean"], 1)],
                ["Медиана", ru(tc["len_median"]), ru(dc["len_median"])],
                ["95-й перцентиль", ru(tc["len_p95"]), ru(dc["len_p95"])],
                ["99-й перцентиль", ru(tc["len_p99"]), ru(dc["len_p99"])],
                ["Максимум", f"{tc['len_max']}", f"{dc['len_max']}"],
                ["Содержит цифры", pct(tc["has_digit_share"]), pct(dc["has_digit_share"])],
                [
                    "Содержит HTML-теги",
                    pct(tc["has_html_tag_share"]),
                    pct(dc["has_html_tag_share"]),
                ],
                [
                    "Содержит переносы строк",
                    pct(tc["has_newline_share"]),
                    pct(dc["has_newline_share"]),
                ],
            ],
            col_widths=[6.0 * cm, 5.0 * cm, 5.0 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            "Заголовки короткие и плотные (медиана 43 символа), почти всегда содержат цифры и латиницу — "
            "это основная зона для извлечения бренда, модели и ключевых параметров. Описания длинные и "
            "почти в половине случаев содержат HTML-разметку, которую нужно чистить перед извлечением.",
            "body",
        ),
    ]
    story += fig_block("14_card_markup.png", "Рис. 4. Разметка и служебные элементы в тексте.")
    story += fig_block("15_title_lang.png", "Рис. 5. Языковой состав заголовков.")
    story += [
        P(
            f"Язык: <b>{pct(c['title_lang_mix'].get('RU+EN', 0) / c['n_rows'])}</b> заголовков смешанные "
            f"(кириллица + латиница: бренд/модель латиницей, тип товара — по-русски), "
            f"{pct(c['title_lang_mix'].get('RU', 0) / c['n_rows'])} — только кириллица. "
            "Это подтверждает, что нормализация должна уметь сопоставлять латинские бренды и русские термины.",
            "body",
        ),
        P("4.1. Качество текста и аномалии", "h2"),
    ]
    story += fig_block("21_dup_anomalies.png", "Рис. 6. Дубликаты и повторяющиеся шаблоны.")
    story.append(
        make_table(
            ["Признак", "Доля / значение"],
            [
                [
                    "Дубликаты заголовков",
                    f"{ru(c['dup_titles'])} ({pct(c['dup_titles'] / c['n_rows'])})",
                ],
                [
                    "Дубликаты описаний",
                    f"{ru(c['dup_descriptions'])} ({pct(c['dup_descriptions'] / c['n_rows'])})",
                ],
                [
                    "Маркер «Лучшие товары из Китая»",
                    ru(c["description_markers"]["Лучшие товары из Китая"]),
                ],
                ["Маркер «Характеристики:»", ru(c["description_markers"]["Характеристики:"])],
                ["Маркер «Комплектация:»", ru(c["description_markers"]["Комплектация:"])],
                ["URL в описании", pct(dc["has_url_share"])],
                ["Мойибейк / битая кодировка", pct(dc["mojibake_share"])],
            ],
            col_widths=[10.0 * cm, 6.0 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            f"Почти <b>{pct(c['dup_titles'] / c['n_rows'])}</b> заголовков повторяются — например, «Косметичка UNIMALL -» "
            "встречается сотни раз. Это типичные «пустые» карточки без конкретики: их нельзя использовать как "
            "самостоятельные примеры, атрибуты придётся брать из описания. Большая доля описаний содержит "
            "рекламные «шаблоны» продавцов — их следует вырезать как шум.",
            "body",
        ),
        PageBreak(),
    ]
    return story


def _section_catalog(D):
    cat = D["catalog"]
    lt = cat["long_tail_params"]
    story = [P("5. Каталог: категории и параметры", "h1")]
    story.append(
        P(
            f"Каталог содержит <b>{ru(cat['n_offers'])}</b> офферов в <b>{ru(cat['n_categories_used'])}</b> категориях. "
            f"Среднее число параметров на оффер — <b>{ru(cat['params_per_offer_mean'], 1)}</b> "
            f"(медиана {ru(cat['params_per_offer_median'])}, максимум {cat['params_per_offer_max']}).",
            "body",
        )
    )
    story += fig_block("04_params_per_offer.png", "Рис. 7. Распределение числа атрибутов на оффер.")
    story += fig_block("09_category_sizes.png", "Рис. 8. Крупнейшие категории каталога.")
    story += [
        P("5.1. Словарь атрибутов и длинный хвост", "h2"),
        P(
            f"После слияния дублей с суффиксом <font face='DejaVu-Mono'>_search</font> остаётся "
            f"<b>{ru(cat['n_distinct_param_names'])}</b> уникальных имён атрибутов "
            f"(сырых — <b>{ru(cat['n_distinct_param_names_raw'])}</b>, из них "
            f"{pct(cat['search_suffixed_share'])} с суффиксом <font face='DejaVu-Mono'>_search</font>). "
            f"Распределение крайне неравномерное: <b>{ru(lt['gt_10000'])}</b> имён встречаются более 10 000 раз, "
            f"а <b>{ru(lt['lt_100'])}</b> — реже 100 раз, <b>{ru(lt['lt_5'])}</b> — реже 5 раз.",
            "body",
        ),
    ]
    story += fig_block(
        "05_param_longtail.png", "Рис. 9. Частотный спектр и длинный хвост имён атрибутов."
    )
    story += fig_block("06_top_params.png", "Рис. 10. Топ-30 имён параметров.")
    story += [
        P(
            "Обратите внимание: верхние строки рейтинга — не товарные характеристики, а служебные и "
            "маркетинговые поля: <b>Подборки</b>, <b>Продавец</b>, <b>Потратить бонусы</b>, "
            "<b>Гарантия</b>, <b>Гарантия предоставляется</b>, <b>Страна</b>. Их обязательно нужно "
            "исключать из целевой схемы извлечения.",
            "body",
        ),
    ]
    story += fig_block(
        "08_param_cardinality.png",
        "Рис. 11. Частота vs кардинальность (цвет — доля числовых значений).",
    )
    story.append(
        P(
            "Диаграмма разделяет атрибуты на два класса: числовые с низкой кардинальностью (размеры, вес, "
            "мощность) и категориальные/текстовые с высокой кардинальностью (модели, серии, артикулы). "
            "Первый класс хорошо закрывается правилами и единицами измерения; второй — длинный хвост, "
            "требующий ML/LLM и словарей.",
            "body",
        )
    )
    story.append(PageBreak())
    return story


def _code_attr_rows(category, order, codes, m):
    if category not in order:
        return []
    i = order.index(category)
    return [
        [code, config.TARGET_ATTRIBUTES[code]["label"], pct(m[i, j])]
        for j, code in enumerate(codes)
        if not np.isnan(m[i, j])
    ]


def _section_focus(D):
    story = [P("6. Целевые категории и атрибуты", "h1")]
    story.append(
        P(
            "Ниже — заполненность ключевых атрибутов по 12 важнейшим категориям электроники кейса. "
            "Значения — доля офферов, у которых атрибут заполнен и попадает в фильтры поиска. "
            "Коды атрибутов соответствуют доменной модели "
            "(<font face='DejaVu-Mono'>openspec/specs/domain-model.md</font>): "
            "<font face='DejaVu-Mono'>brand</font>, <font face='DejaVu-Mono'>model</font>, "
            "<font face='DejaVu-Mono'>color</font>, <font face='DejaVu-Mono'>storage</font>, "
            "<font face='DejaVu-Mono'>drive</font>, <font face='DejaVu-Mono'>ram</font>, "
            "<font face='DejaVu-Mono'>diagonal</font>, "
            "<font face='DejaVu-Mono'>battery_capacity</font>, "
            "<font face='DejaVu-Mono'>processor</font>.",
            "body",
        )
    )
    story += fig_block(
        "10_focus_heatmap.png",
        "Рис. 12. Заполненность целевых атрибутов по категориям. Серые ячейки («—») — "
        "атрибут отсутствует в схеме категории; цветовая шкала нормирована на фактический "
        "диапазон данных, чтобы была видна разница между высокими значениями.",
        max_h=15 * cm,
    )
    story += fig_block(
        "11_smartphone_attrs.png",
        "Рис. 13. Атрибуты смартфонов: заполненность и число уникальных значений.",
        max_h=16 * cm,
    )
    story.append(P("6.1. Пример схемы атрибутов смартфона", "h2"))
    focus = pd.read_parquet(config.CACHE_DIR / "focus_attrs.parquet")
    sub = focus[focus.category_name == "Смартфоны"].head(14)
    rows = [
        [
            str(r.param),
            ru(r.n_offers),
            pct(r.fill_rate),
            ru(r.n_distinct),
            str(r.top_values)[:48],
        ]
        for r in sub.itertuples()
    ]
    story.append(
        make_table(
            ["Атрибут", "Офферов", "Заполнено", "Уник. знач.", "Топ-значения"],
            rows,
            col_widths=[4.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 5.2 * cm],
            font_size=8,
        )
    )
    story += [
        Spacer(1, 6),
        P("6.2. Пример схемы атрибутов ноутбука", "h2"),
    ]
    sub = focus[focus.category_name == "Ноутбуки"].head(12)
    rows = [
        [
            str(r.param),
            ru(r.n_offers),
            pct(r.fill_rate),
            ru(r.n_distinct),
            str(r.top_values)[:48],
        ]
        for r in sub.itertuples()
    ]
    story.append(
        make_table(
            ["Атрибут", "Офферов", "Заполнено", "Уник. знач.", "Топ-значения"],
            rows,
            col_widths=[4.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 5.2 * cm],
            font_size=8,
        )
    )
    story += [
        Spacer(1, 6),
        P("Наблюдения по схемам:", "h2"),
        *bullets(
            [
                "Ядро схемы повторяется: бренд, модель, цвет, материалы, габариты/вес, страна. "
                "Дальше — категорийные атрибуты (память, экран, процессор для смартфонов; ОС, клавиатура для ноутбуков).",
                "Атрибуты-«двойники» хранятся в каталоге отдельными параметрами («Встроенная память» и "
                "«Встроенная память (ROM)», «Оперативная память» и «Оперативная память (RAM)») — при анализе "
                "они сведены к единым кодам <font face='DejaVu-Mono'>storage</font> и "
                "<font face='DejaVu-Mono'>ram</font>.",
                "Встроенная память (<font face='DejaVu-Mono'>storage</font>) и накопитель "
                "(<font face='DejaVu-Mono'>drive</font>) — разные атрибуты: у смартфонов заполнена "
                "встроенная память, у ноутбуков — накопитель (SSD/HDD).",
                'Часть полей — ведра/диапазоны для фильтров: «Диагональ экрана» = «6.6" и более», '
                "«Емкость аккумулятора» = «3000-5000 мАч». Рядом живёт точное значение («Диагональ» = 6.7). "
                "Это два разных представления одного атрибута.",
                "Есть полностью служебные поля, которые не являются товарными характеристиками "
                "(«ЗД для отчета BI/BO», «Продавец», «Подборки», «Гарантия предоставляется», «Потратить бонусы»).",
                "Бренд и модель заполнены в 100% офферов — это самые надёжные атрибуты и хорошие "
                "первичные ключи для сопоставления товаров.",
            ]
        ),
    ]
    order, codes, m = plotting._focus_fill_matrix()
    story += [
        Spacer(1, 8),
        P("6.3. Коды доменной модели для приёмочных категорий", "h2"),
        P(
            "Соответствие кодов атрибутов доменной модели для категорий из приёмочных тест-кейсов "
            "(<font face='DejaVu-Mono'>openspec/specs/attribute_extractor.md</font>, §7.4). "
            "Заполнено — доля офферов с атрибутом в каталоге.",
            "body",
        ),
    ]
    for cname in ["Смартфоны", "Ноутбуки"]:
        story.append(P(f"<b>{cname}</b>", "body"))
        story.append(
            make_table(
                ["Код", "Атрибут", "Заполнено"],
                _code_attr_rows(cname, order, codes, m),
                col_widths=[4.0 * cm, 7.0 * cm, 4.0 * cm],
                font_size=9,
            )
        )
        story.append(Spacer(1, 6))
    story.append(PageBreak())
    return story


def _section_normalization(D):
    st, sc, cl = D["storage"], D["diagonal"], D["color"]
    story = [P("7. Нормализация значений и единиц", "h1")]
    story.append(
        P(
            "Отдельный слой анализа — насколько «грязны» значения. Ключевое наблюдение: "
            "в структурированном каталоге значения в основном уже приведены к словарю и единицам, "
            "но форматы всё ещё расходятся, а входной текст карточек не нормализован вовсе.",
            "body",
        )
    )
    story += fig_block("07_units.png", "Рис. 14. Структурированные единицы измерения (@unit).")
    story += [
        P(
            "Единицы в поле <font face='DejaVu-Mono'>@unit</font> каталога стандартизованы "
            "(см, кг, шт, мм, Вт, ГБ...), но многие числовые атрибуты хранят единицу прямо в значении "
            "без <font face='DejaVu-Mono'>@unit</font> («Высота» = «30 см»). То есть пайплайн должен "
            "уметь разбирать число и единицу и из значения, и из отдельного поля.",
            "body",
        ),
    ]
    story += fig_block(
        "17_value_formats.png", "Рис. 15. Форматы значений для памяти и диагонали экрана."
    )
    story.append(
        make_table(
            ["Атрибут", "Всего значений", "Уникальных", "Основные форматы"],
            [
                [
                    "Встроенная память",
                    ru(st["total_values"]),
                    ru(st["distinct_values"]),
                    ", ".join(f"{k}: {ru(v)}" for k, v in st["format_counts"].items()),
                ],
                [
                    "Диагональ экрана",
                    ru(sc["total_values"]),
                    ru(sc["distinct_values"]),
                    ", ".join(f"{k}: {ru(v)}" for k, v in sc["format_counts"].items()),
                ],
                [
                    "Цвет",
                    ru(cl["total_values"]),
                    ru(cl["distinct_values"]),
                    f"после lower/ё: {ru(cl['distinct_after_lower_norm'])}, коллизий: {ru(cl['collision_count'])}",
                ],
            ],
            col_widths=[3.6 * cm, 3.0 * cm, 2.6 * cm, 6.8 * cm],
            font_size=8,
        )
    )
    story += [
        Spacer(1, 6),
        P(
            f"Память: всего {ru(st['distinct_values'])} уникальных значений — словарь уже узкий, "
            "но диагональ хранится и в дюймах, и просто числом, и в виде диапазонов («от 15 до 16.9»). "
            f"Цвет: {ru(cl['distinct_values'])} уникальных значений, из которых "
            f"{ru(cl['distinct_values'] - cl['distinct_after_lower_norm'])} — дубликаты по регистру и букве «ё» "
            "(«черный»/«чёрный»/«Черный»), плюс составные цвета через слэш.",
            "body",
        ),
    ]
    story += fig_block(
        "18_color_messiness.png", "Рис. 16. Топ значений цвета и дубликаты после нормализации."
    )
    story += [
        P("Примеры коллизий цвета (разные написания одного значения):", "small"),
    ]
    coll = D["color"]["collisions_sample"]
    sample = list(coll.items())[:12]
    rows = [
        [str(k), ", ".join(f"{v} ({cnt})" for v, cnt in list(vals.items())[:5])]
        for k, vals in sample
    ]
    story.append(
        make_table(
            ["Каноническое (после lower/ё)", "Варианты написания"],
            rows,
            col_widths=[6.0 * cm, 10.0 * cm],
            font_size=8,
        )
    )
    story.append(PageBreak())
    return story


def _section_traffic(D):
    t = D["traffic"]
    q = t["price_quantiles"]
    story = [P("8. Кликовый трафик", "h1")]
    story.append(
        P(
            f"Трафик — источник весов важности атрибутов: <b>{ru(t['n_rows'])}</b> показов/кликов, "
            f"<b>{ru(t['n_unique_sku'])}</b> SKU, <b>{ru(t['n_unique_subject'])}</b> тематик. "
            "Атрибуты, по которым чаще фильтруют и которые чаще встречаются в популярных категориях, "
            "приносят больше пользы и должны весить больше в метрике.",
            "body",
        )
    )
    story += fig_block(
        "03_category_traffic.png", "Рис. 17. Топ-20 категорий по кликовому трафику.", max_h=16 * cm
    )
    story += [
        P(
            "Самые «трафиковые» категории — бытовая техника и электроника: стиральные машины, "
            "холодильники, телевизоры, ноутбуки, смартфоны, наушники. Именно здесь заполненность "
            "атрибутов напрямую влияет на CTR и конверсию.",
            "body",
        ),
    ]
    story += fig_block("19_prices.png", "Рис. 18. Распределение цен в трафике.")
    story.append(
        make_table(
            ["Метрика цены", "Значение, ₽"],
            [
                ["Средняя", ru(t["price_mean"])],
                ["Медиана", ru(t["price_median"])],
                ["1-й перцентиль", ru(q["0.01"])],
                ["99-й перцентиль", ru(q["0.99"])],
                ["Максимум", ru(t["price_max"])],
                ["Доля нулевых цен", pct(t["price_zero_share"])],
            ],
            col_widths=[8.0 * cm, 8.0 * cm],
        )
    )
    story += [
        Spacer(1, 6),
        P(
            f"Аномалия: <b>{ru(int(t['price_zero_share'] * t['n_rows']))}</b> строк с нулевой ценой "
            f"({pct(t['price_zero_share'])}) — товары без цены, их нужно исключать из ценовых признаков. "
            "Отрицательных цен нет. Распределение цен логнормальное с длинным правым хвостом "
            f"(максимум {ru(t['price_max'])} ₽).",
            "body",
        ),
    ]
    story += fig_block("20_position.png", "Рис. 19. Распределение кликов по позициям в выдаче.")
    story.append(
        P(
            f"Кликовый трафик сконцентрирован в начале выдачи: позиция 0 даёт "
            f"<b>{pct(t['position_0_share'])}</b> кликов. Максимальная позиция — {ru(t['position_max'])}. "
            "Это подтверждает ценность корректных атрибутов: они поднимают товар в фильтрах и "
            "в самых горячих позициях.",
            "body",
        )
    )
    story.append(PageBreak())
    return story


def _section_anomalies(D):
    c, cat = D["cards"], D["catalog"]
    story = [P("9. Сводка аномалий и проблем данных", "h1")]
    story.append(
        make_table(
            ["#", "Проблема", "Масштаб", "Как учитывать"],
            [
                [
                    "1",
                    "Низкое пересечение источников",
                    f"{ru(D['coverage']['overlap']['offers_cards'])} SKU (текст+эталон)",
                    "обучаться/валидироваться только на пересечении",
                ],
                [
                    "2",
                    "Дубликаты заголовков карточек",
                    f"{pct(c['dup_titles'] / c['n_rows'])}",
                    "дедуплицировать, брать атрибуты из описания",
                ],
                [
                    "3",
                    "HTML-разметка в описаниях",
                    pct(c["columns"]["description"]["has_html_tag_share"]),
                    "очистка тегов перед извлечением",
                ],
                [
                    "4",
                    "Маркетинговые «шаблоны» продавцов",
                    ru(c["description_markers"]["Лучшие товары из Китая"]) + " вхождений фразы",
                    "вырезать как шум",
                ],
                [
                    "5",
                    "Служебные «атрибуты» в каталоге",
                    "Подборки, Продавец, Гарантия, BI-поля",
                    "исключить из целевой схемы",
                ],
                [
                    "6",
                    "Атрибуты-двойники",
                    "«Встроенная память» / «(ROM)»",
                    "канонизировать в один код",
                ],
                [
                    "7",
                    "Ведра/диапазоны вместо значений",
                    '«6.6" и более», «3000-5000 мАч»',
                    "различать точное значение и фильтр-фасет",
                ],
                [
                    "8",
                    "Длинный хвост атрибутов",
                    f"{ru(cat['long_tail_params']['lt_100'])} имён < 100 вхождений",
                    "правила + ML/LLM, не только словарь",
                ],
                [
                    "9",
                    "Грязь цвета (регистр, ё, составные)",
                    f"{ru(D['color']['collision_count'])} групп коллизий",
                    "lowercase + ё→е + словарь цветов",
                ],
                [
                    "10",
                    "Нулевые цены в трафике",
                    pct(D["traffic"]["price_zero_share"]),
                    "исключать из ценовых признаков",
                ],
                [
                    "11",
                    "Цвет почти не заземляется в тексте",
                    pct(D["coverage"]["grounding"]["color"]["any"]),
                    "извлекать из структуры/словаря, не из текста",
                ],
                [
                    "12",
                    "Смешение языков и транслитерация",
                    pct(c["title_lang_mix"]["RU+EN"] / c["n_rows"]) + " заголовков RU+EN",
                    "нормализация латиница↔кириллица",
                ],
            ],
            col_widths=[0.8 * cm, 4.6 * cm, 5.2 * cm, 6.4 * cm],
            font_size=8,
        )
    )
    story.append(PageBreak())
    return story


def _section_recommendations(D):
    story = [P("10. Выводы и рекомендации", "h1")]
    story.append(P("10.1. Что показал EDA", "h2"))
    story += bullets(
        [
            "Данные полуструктурированы: <b>эталон атрибутов лежит в структурированных параметрах каталога</b>, "
            "а неструктурированный вход — это текст карточек. Пайплайн должен соединять оба мира.",
            "Ядро атрибутов (бренд, модель, цвет, материалы, габариты) повторяется почти во всех категориях — "
            "его можно закрыть правилами и словарями. Категорийный хвост и редкие значения — зона ML/LLM.",
            "Бренд и модель хорошо извлекаются из заголовка (98% и 96%). Цвет — нет (17%): нужен словарь и "
            "структурный источник.",
            "Таксономия огромна (10,7к имён атрибутов), с сильным длинным хвостом — единая ручная разметка "
            "невозможна, нужна автоматическая канонизация на базе словарей каталога.",
        ]
    )
    story.append(P("10.2. Рекомендации по пайплайну", "h2"))
    story += bullets(
        [
            "<b>Источник схемы атрибутов</b>: строить канонический реестр атрибутов из параметров каталога по категории, "
            "отфильтровав служебные поля (Подборки, Продавец, Гарантия, BI-поля).",
            "<b>Словарь значений</b>: взять допустимые значения атрибутов прямо из каталога "
            "(память, цвет, диагональ уже почти нормализованы) — это даёт бесплатный grounding и валидацию.",
            "<b>Препроцессинг текста</b>: снятие HTML, удаление рекламных «шаблонов», нормализация пробелов, "
            "регистра и ё→е, транслитерация брендов.",
            "<b>Каскад cheap-first</b>: правила/словари для ядра и числовых полей → NER/классификатор для хвоста → "
            "LLM только на нетиповых карточках с ограничением схемой вывода.",
            "<b>Категория</b>: карточки sku_desc не содержат категорию — определять её классификатором по тексту "
            "или подтягивать из каталога по SKU на этапе валидации.",
            "<b>Метрика</b>: считать precision/recall/F1 по каждому атрибуту и взвешивать по трафику "
            "(query_clicks) — приоритет отдавать атрибутам горячих категорий.",
            "<b>Валидация</b>: hold-out на подмножестве SKU с текстом и трафиком; отдельно контролировать "
            "редкие категории и редкие значения.",
        ]
    )
    story.append(P("10.3. Риски", "h2"))
    story += bullets(
        [
            "Галлюцинации LLM — ограничить схемой и проверкой заземления значения в тексте.",
            "Дисбаланс по категориям — контролировать метрику на редких категориях отдельно.",
            "Низкое пересечение источников ограничивает объём размеченных пар «текст → атрибуты».",
            "Дрейф каталога (новые товары/категории) — правила и словари нужно регулярно обновлять.",
        ]
    )
    story.append(Spacer(1, 10))
    story.append(
        P(
            "Артефакты EDA: <font face='DejaVu-Mono'>EDA/figures/</font> (21 график), "
            "<font face='DejaVu-Mono'>EDA/results/</font> (таблицы CSV), "
            "<font face='DejaVu-Mono'>EDA/cache/</font> (агрегаты), "
            "<font face='DejaVu-Mono'>EDA/src/</font> (воспроизводимый код).",
            "small",
        )
    )
    return story


def run():
    print("[report] building ...")
    D = _load()
    doc = _Doc(str(config.REPORT_PATH))
    story = []
    story += _title_page(D)
    story += _section_summary(D)
    story += _section_sources(D)
    story += _section_coverage(D)
    story += _section_cards(D)
    story += _section_catalog(D)
    story += _section_focus(D)
    story += _section_normalization(D)
    story += _section_traffic(D)
    story += _section_anomalies(D)
    story += _section_recommendations(D)
    doc.build(story)
    print(f"[report] -> {config.REPORT_PATH}")
