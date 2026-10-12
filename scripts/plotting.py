"""Shared figure style and drawing for the visualise_* notebooks.

Every decision about how a figure looks lives in the `plotting` block of
config/default.yaml; this module applies it. The notebooks choose *what* to
draw and call in here to draw it, so the demand figures and the comparison
figures share one bar stack, one panel grid and one save path instead of a copy
each.

The notebooks import this by path (`sys.path.insert(0, repo / "scripts")`): a
snakemake `notebook:` rule executes the notebook from the repo root but does not
put scripts/ on sys.path.
"""

import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.transforms as mtransforms
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.legend_handler import HandlerBase
from matplotlib.textpath import TextToPath

# Measures a string in points without a renderer, which is what `label_points`
# needs: no renderer exists before the figure is drawn, and forcing a draw there
# would fight constrained layout. It reads the font itself, so a name set bold
# or italic is measured as it will be drawn rather than as an average glyph.
_TEXT_METRICS = TextToPath()

# What `panel_title` leaves between the axes and the title before `extra_pad`,
# with and without a subtitle in between. `band_title_pad` measures off it.
TITLE_PAD = 8.0
SUBTITLE_PAD = 17.0

# `reference_lines` name geometry: points of blank before the first row, then the
# depth of a row and the gap between two names on one, in multiples of their size.
LINE_NAME_PAD = 3.0
LINE_NAME_PITCH = 1.35
LINE_NAME_AIR = 0.9

# Patch keywords a bar may not carry per row. A stroke is drawn centred on the
# rectangle, half of it outside, so the edge decides how wide a bar *reads*:
# `bar.edge_color` is the page's own white, invisible outside the bar and eating
# into the fill inside it, while a coloured stroke of the same width shows on
# both sides. One row edged differently is drawn at the shared width and read at
# a wider one — which is a difference in the data everywhere else on the figure.
# A legend swatch sits on no shared axis, so `styled_patch_handles` may still
# outline it.
FOOTPRINT_KEYS = frozenset({"edgecolor", "ec", "linewidth", "lw"})


# Which of a panel's two axes the bars are named on. Every function drawing into a
# bar panel takes the same `orientation`, so turning a figure on its side is one
# argument rather than a second implementation of everything in it.
_BAR_AXIS = {"vertical": ("x", "y"), "horizontal": ("y", "x")}


def bar_axes(orientation: str) -> tuple[str, str]:
    """The (category, value) axis names for `orientation`."""
    if orientation not in _BAR_AXIS:
        raise ValueError(
            f"orientation must be one of {sorted(_BAR_AXIS)}, not {orientation!r}"
        )
    return _BAR_AXIS[orientation]


def category_limits(
    positions: dict[str, float], plotting: dict, panel_key: str = "panel"
) -> tuple[float, float]:
    """The span of a bar axis: every position, plus half a bar of margin either end.

    Read by `category_axis` and by anything drawn on the same scale beside it --
    the column of names `flow_panel_grid` puts at the left of a row, which has to
    line up with panels it shares no axis with.
    """
    margin = 0.5 + plotting[panel_key]["bar_width"] / 2
    return min(positions.values()) - margin, max(positions.values()) + margin


def turned_figure_size(
    positions: dict[str, float], plotting: dict, panel_key: str
) -> tuple[float, float]:
    """The size of a figure whose single axes carries `positions` as horizontal bars.

    The bar axis is the height here, so it is bought rather than divided up:
    `bar_pitch` an inch per bar and per unit of blank between the groups, plus
    `chrome` for the value axis. Only what constrained layout reserves counts as
    `chrome`; a name outside the axes goes to `save_figure`'s tight box instead.
    """
    panel = plotting[panel_key]
    low, high = category_limits(positions, plotting, panel_key)
    return panel["width"], (high - low) * panel["bar_pitch"] + panel["chrome"]


def apply_style(plotting: dict) -> None:
    """Adopt the shared rcParams. Call once, before anything is drawn."""
    mpl.rcParams.update(plotting["rcparams"])


def grouped_members(
    members, member_group: dict[str, str], groups
) -> dict[str, list[str]]:
    """`members` blocked by the group each one claims, in `groups` order.

    `member_group` is the whole partition and `groups` only the block order, so a
    block need not be contiguous in `members`. An empty block is dropped; a group
    `groups` does not declare raises.
    """
    members = list(members)
    undeclared = sorted({member_group[member] for member in members} - set(groups))
    if undeclared:
        raise ValueError(
            f"{undeclared} are claimed as groups but not declared, so there is no "
            "order or display name for them"
        )
    blocked = {
        group: [member for member in members if member_group[member] == group]
        for group in groups
    }
    return {group: block for group, block in blocked.items() if block}


def bar_positions(
    groups: dict[str, list[str]], plotting: dict, gap: float | None = None
) -> dict[str, float]:
    """Position of every member of `groups`, with blank space between the groups.

    Members are laid out one unit apart in the order the groups declare them,
    and `bar.group_gap` of nothing is inserted at each group boundary, so the
    members that answer the same question read as a block.

    `gap` overrides that shared gap, for a figure whose page size follows the bar
    axis rather than the other way round: a row of `flow_panel_grid` is as tall
    as this axis is long, so the blank space in it is bought with page.
    """
    gap = plotting["bar"]["group_gap"] if gap is None else gap
    positions: dict[str, float] = {}
    cursor = 0.0
    for index, members in enumerate(groups.values()):
        if index:
            cursor += gap
        for member in members:
            positions[member] = cursor
            cursor += 1.0
    return positions


def stacked_bars(
    ax,
    positions: dict[str, float],
    frame: pd.DataFrame,
    colors: dict[str, str],
    plotting: dict,
    bottom: float | np.ndarray = 0.0,
    panel_key: str = "panel",
    row_styles: dict[str, dict] | None = None,
    orientation: str = "vertical",
) -> np.ndarray:
    """One stacked bar per row of `frame`, and the far end of each stack back.

    `frame` is indexed by the keys of `positions`, one column per segment in
    stacking order. `bottom` starts the stack somewhere other than zero, which a
    log axis needs (a segment rising from zero has no lower edge to draw) and
    which is also how a second stack is placed on top of a first. `panel_key`
    is the panel spec being drawn into, which carries the bar width.
    `orientation` of "horizontal" lays the same stack along x instead.

    `row_styles` sets individual bars apart from the rest — a dict per row of
    keyword arguments for its Patch, applied to every segment of that row — so a
    stack can carry a second, quieter encoding in how it is filled rather than
    in another mark. It is `category_axis`'s `label_styles` for the bar instead
    of the label, and takes the same dicts `styled_patch_handles` keys them with.
    It may only change the fill: `FOOTPRINT_KEYS` are refused, because a bar that
    is drawn at the shared width but read at another one says something about the
    data that is not true.
    """
    bar = plotting["bar"]
    # ax.bar's bottom is ax.barh's left, and its width its height.
    draw, thickness_key, start_key = (
        (ax.bar, "width", "bottom")
        if bar_axes(orientation) == ("x", "y")
        else (ax.barh, "height", "left")
    )
    if row_styles is not None:
        offending = {
            key: sorted(FOOTPRINT_KEYS & set(spec)) for key, spec in row_styles.items()
        }
        offending = {key: keys for key, keys in offending.items() if keys}
        if offending:
            raise ValueError(
                f"row_styles may not set {sorted(FOOTPRINT_KEYS)}, which change how "
                f"wide a bar reads: {offending}"
            )
    x = np.array([positions[key] for key in frame.index])
    top = np.broadcast_to(np.asarray(bottom, dtype=float), x.shape).copy()
    for segment in frame.columns:
        values = frame[segment].to_numpy()
        drawn = draw(
            x,
            values,
            color=colors[segment],
            edgecolor=bar["edge_color"],
            linewidth=bar["edge_width"],
            **{
                thickness_key: plotting[panel_key]["bar_width"],
                start_key: top,
            },
        )
        if row_styles is not None:
            for key, patch in zip(frame.index, drawn.patches):
                patch.set(**row_styles[key])
        top = top + values
    return top


def _label_rows(
    ax, levels: dict[str, float], labels: dict[str, str], size: float, air: float
) -> dict[str, int]:
    """Which row beyond the panel each level's name takes, counting from the panel.

    Each name takes the row nearest the panel with room for it at its own line.
    Rows fill right to left, so a name placed later starts left of everything
    already down and no line rises through another name.

    Widths come from `_TEXT_METRICS` (no renderer) and positions from the axes,
    so the value axis has to be limited first. Constrained layout has not run,
    leaving the panel narrow: the error is a spare row, never an overlap.
    """
    scale = ax.figure.dpi / 72.0  # points -> display pixels
    prop = FontProperties(size=size)
    taken: list[float] = []  # the leftmost point each row is spoken for at
    rows = {}
    for key in sorted(levels, key=lambda key: levels[key], reverse=True):
        width, _, _ = _TEXT_METRICS.get_text_width_height_descent(
            labels[key], prop, ismath=False
        )
        start = ax.transData.transform((levels[key], 0.0))[0]
        finish = start + (width + air) * scale
        row = next(
            (row for row, used in enumerate(taken) if finish <= used), len(taken)
        )
        taken[row : row + 1] = [start]
        rows[key] = row
    return rows


def reference_lines(
    ax,
    levels: dict[str, float],
    styles: dict[str, dict],
    color_key: str,
    style_key: str,
    labels: dict[str, str] | None = None,
    orientation: str = "vertical",
    tuck_longest: bool = False,
) -> list:
    """A line across the panel per entry of `levels`, drawn in that entry's style.

    The line crosses the value axis, so it is horizontal over vertical bars and
    vertical over horizontal ones -- `orientation` is the bars', not the line's.

    `labels` names them at the far end of the axis instead of in the legend, each
    in its own line's colour: it costs no legend row, and saves the reader matching
    three dashes to three entries in a key. A name lies level
    either way, so over horizontal bars the names go above the panel in rows
    (`_label_rows`) and each line carries on past the panel to its own.

    `tuck_longest` sets the longest name under its own line instead, ending where
    the next longest does, so the margin beside the panel is no wider than that
    one needs. Names beside their lines only, so upright panels only.

    Those names sit outside the axes, so they are returned for `save_figure`'s
    `extra_artists`: passing that argument at all replaces matplotlib's own
    collection, and a name left out of it is cropped away mid-word.
    """
    upright = bar_axes(orientation) == ("x", "y")
    size = mpl.rcParams["xtick.labelsize"]
    # The name sits hard against the end of the line, on the axis the line
    # crosses: one axis in data and the other in axes fraction, either way.
    axline, across, place = (
        (ax.axhline, ax.get_yaxis_transform, lambda level: (1.0, level))
        if upright
        else (ax.axvline, ax.get_xaxis_transform, lambda level: (level, 1.0))
    )
    rows = (
        {}
        if labels is None or upright
        else _label_rows(ax, levels, labels, size, LINE_NAME_AIR * size)
    )
    tucked, reach = None, 0.0
    if tuck_longest:
        if not upright or labels is None or len(levels) < 2:
            raise ValueError(
                "tuck_longest sets a name under its line beside the panel, so it "
                "needs an upright panel and at least two named lines"
            )
        prop = FontProperties(size=size)
        width = {
            key: _TEXT_METRICS.get_text_width_height_descent(labels[key], prop, ismath=False)[0]
            for key in levels
        }
        tucked, runner_up = sorted(width, key=width.get, reverse=True)[:2]
        reach = width[runner_up]
    names = []
    for key, level in levels.items():
        axline(
            level,
            color=styles[key][color_key],
            linestyle=styles[key][style_key],
            linewidth=1.1,
            zorder=3,
        )
        if labels is not None:
            if key == tucked:
                offset, ha, va = (LINE_NAME_PAD + reach, -LINE_NAME_PAD), "right", "top"
            elif upright:
                offset, ha, va = (LINE_NAME_PAD, 0.0), "left", "center"
            else:
                offset = (0.0, LINE_NAME_PAD + rows[key] * LINE_NAME_PITCH * size)
                ha, va = "left", "bottom"
            names.append(
                ax.annotate(
                    labels[key],
                    xy=place(level),
                    xycoords=across(),
                    xytext=offset,
                    textcoords="offset points",
                    ha=ha,
                    va=va,
                    # The line's extension to the name, tailed at the name's own
                    # bottom-left corner so that it runs straight up its line.
                    arrowprops=None
                    if upright
                    else {
                        "arrowstyle": "-",
                        "relpos": (0.0, 0.0),
                        "shrinkB": 0.0,
                        "color": styles[key][color_key],
                        "linestyle": styles[key][style_key],
                        "linewidth": 1.1,
                    },
                    fontsize=size,
                    color=styles[key][color_key],
                    annotation_clip=False,
                    zorder=3,
                )
            )
    return names


def page_figure(
    plotting: dict,
    aspect: float | None = None,
    height: float | None = None,
    ncols: int = 1,
    **gridspec_kw,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """A figure the page wide, carrying `ncols` axes side by side.

    `page_width` is the width of every figure here, so a caller says only how
    tall this one is: `aspect` as a multiple of that width, or `height` in
    inches where the height follows the data. Neither takes `supplement.aspect`.
    `gridspec_kw` goes to the subplots, which is how a figure whose panels are
    not the same width says so (`width_ratios`).
    """
    if aspect is not None and height is not None:
        raise ValueError(
            "a figure's height is either an `aspect` of the page width or a "
            "`height` in inches, not both"
        )
    width = plotting["page_width"]
    if height is None:
        height = width * (
            plotting["supplement"]["aspect"] if aspect is None else aspect
        )
    fig, axes = plt.subplots(
        1, ncols, figsize=(width, height), layout="constrained",
        squeeze=False, gridspec_kw=gridspec_kw,
    )
    return fig, list(axes[0])


def _grid_shape(
    count: int,
    plotting: dict,
    max_columns: int | None,
    panel_aspect: float | None,
    row_height: float | None,
) -> tuple[int, float]:
    """How many columns a grid of `count` panels takes, and how tall a row is.

    Apart from the figure so that `paged_cell_grid` can measure the whole grid
    once and draw every page to that same shape: a panel has to come out the
    same size on the last page as on the first.
    """
    supplement = plotting["supplement"]
    columns = min(
        count, supplement["max_columns"] if max_columns is None else max_columns
    )
    if row_height is None:
        row_height = (plotting["page_width"] / columns) * (
            supplement["panel_aspect"] if panel_aspect is None else panel_aspect
        )
    return columns, row_height


def _grid_figure(
    count: int, columns: int, row_height: float, plotting: dict, **subplots_kw
) -> tuple[plt.Figure, list[plt.Axes]]:
    """`count` panels in a grid `columns` wide, the page's width."""
    rows = int(np.ceil(count / columns))
    fig, axes = plt.subplots(
        rows, columns, figsize=(plotting["page_width"], row_height * rows),
        layout="constrained", squeeze=False, **subplots_kw,
    )
    # Stripped, not hidden: a hidden axes is left out of the tight bounding box
    # `save_figure` crops to, which would print a part-filled page to a scale of
    # its own.
    for axis in axes.flat[count:]:
        axis.set_frame_on(False)
        axis.set_xticks([])
        axis.set_yticks([])
    return fig, list(axes.flat[:count])


def page_grid(
    count: int,
    plotting: dict,
    max_columns: int | None = None,
    panel_aspect: float | None = None,
    row_height: float | None = None,
    **subplots_kw,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """`count` panels flowed across rows of at most `max_columns`, page wide.

    The panels divide the page between them; height is then bought a row at a
    time, either `panel_aspect` of a panel's own width or `row_height` inches
    for a panel as tall as the bars in it. Past a page of it, use `paged_grid`.
    Only the drawn panels come back, in reading order.
    """
    columns, height = _grid_shape(
        count, plotting, max_columns, panel_aspect, row_height
    )
    return _grid_figure(count, columns, height, plotting, **subplots_kw)


def paged_grid(
    members: list,
    plotting: dict,
    max_columns: int | None = None,
    panel_aspect: float | None = None,
    row_height: float | None = None,
    rows: int | None = None,
    **subplots_kw,
):
    """`members` as a panel each, over as many page-tall grids as it takes.

    Two dozen panels do not fit one page at a legible size, and scaling them to
    fit shrinks their text against every other figure's, so the grid is cut at
    `page_height` instead. Every page is drawn to the same shape, full but for
    the last. Yields (figure, its axes, the members drawn on it).

    `rows` fixes how many rows a page carries, each a `rows`th of the page tall,
    in place of a `row_height` or `panel_aspect`.
    """
    members = list(members)
    if rows is not None:
        if row_height is not None or panel_aspect is not None:
            raise ValueError(
                "a page's rows are set by `rows`, or by a `row_height` or "
                "`panel_aspect`, not both"
            )
        row_height = plotting["page_height"] / rows
    columns, height = _grid_shape(
        len(members), plotting, max_columns, panel_aspect, row_height
    )
    if rows is None:
        rows = max(1, int(plotting["page_height"] // height))
    per_page = rows * columns
    for start in range(0, len(members), per_page):
        page = members[start : start + per_page]
        fig, axes = _grid_figure(len(page), columns, height, plotting, **subplots_kw)
        yield fig, axes, page


def _cell_figure(
    count: int, columns: int, ratios: list[float], row_height: float, plotting: dict
) -> tuple[plt.Figure, list[tuple]]:
    """`count` cells of `len(ratios)` panels each, `columns` cells to a row.

    A cell's panels sit in one gridspec with a spacer column of `cell_gap`
    between one cell and the next, so what separates two cells reads wider than
    what separates a cell's own panels.
    """
    gap = plotting["supplement"]["cell_gap"]
    rows = int(np.ceil(count / columns))
    widths, is_panel = [], []
    for index in range(columns):
        if index:
            widths.append(gap)
            is_panel.append(False)
        widths.extend(ratios)
        is_panel.extend([True] * len(ratios))
    fig, grid = plt.subplots(
        rows, len(widths),
        figsize=(plotting["page_width"], row_height * rows),
        layout="constrained", squeeze=False, gridspec_kw={"width_ratios": widths},
    )
    for spacer in grid[:, [i for i, drawn in enumerate(is_panel) if not drawn]].flat:
        spacer.set_visible(False)
    panels = grid[:, [i for i, drawn in enumerate(is_panel) if drawn]]
    cells = [
        tuple(panels[row, cell * len(ratios) : (cell + 1) * len(ratios)])
        for row in range(rows)
        for cell in range(columns)
    ]
    # Stripped, not hidden, for the reason `_grid_figure` gives.
    for cell in cells[count:]:
        for axis in cell:
            axis.set_frame_on(False)
            axis.set_xticks([])
            axis.set_yticks([])
    return fig, cells[:count]


def paged_cell_grid(
    members: list,
    plotting: dict,
    ratios: list[float],
    columns: int,
    row_height: float | None = None,
):
    """`members` as a *cell* each — several panels about one subject — over pages.

    For a member whose panel is really a group of panels: the per-metal supply
    comparison is a line plot and a bar plot about one metal, and two of those
    fit across the page. Yields what `paged_grid` does, the axes as one tuple
    per cell.
    """
    members = list(members)
    if row_height is None:
        row_height = plotting["supplement"]["cell_row"]
    per_page = max(1, int(plotting["page_height"] // row_height)) * columns
    for start in range(0, len(members), per_page):
        page = members[start : start + per_page]
        fig, cells = _cell_figure(len(page), columns, ratios, row_height, plotting)
        yield fig, cells, page


def bar_panel_height(count: int, plotting: dict) -> float:
    """The height of a panel carrying `count` horizontal bars.

    A bar keeps the same `row_pitch` of an inch whatever panel it lands in, so a
    longer ranking costs page rather than squeezing its own labels.
    """
    supplement = plotting["supplement"]
    return count * supplement["row_pitch"] + supplement["panel_chrome"]


def pack_rows(
    groups: dict[str, list[str]], max_columns: int | None
) -> list[list[tuple[str, list[str]]]]:
    """Groups laid out into rows of at most `max_columns` panels.

    A group is never split across rows, so a row holds whole groups only.
    `max_columns` of None gives every group a row to itself however few panels
    it has — right when a panel is a wide scenario axis, wasteful when it is a
    single bar.
    """
    rows: list[list[tuple[str, list[str]]]] = []
    for group, members in groups.items():
        if max_columns is not None and len(members) > max_columns:
            raise ValueError(
                f"group {group!r} has {len(members)} panels, more than the "
                f"{max_columns} a row holds"
            )
        width = sum(len(m) for _, m in rows[-1]) if rows else 0
        if rows and max_columns is not None and width + len(members) <= max_columns:
            rows[-1].append((group, members))
        else:
            rows.append([(group, members)])
    return rows


def panel_grid(
    groups: dict[str, list[str]], plotting: dict, panel_key: str = "panel"
) -> tuple[plt.Figure, dict[str, plt.Axes], list]:
    """A panel per group member, laid out in rows of whole groups.

    Each row is a subfigure whose columns alternate panels with blank spacers of
    `group_gap` panel widths, so where one group ends and the next begins on the
    same row reads wider than the space between two panels of one group. Every
    row is given the same total width — the widest row's panels plus the most
    gaps any row needs — with the slack left at the end, so a panel comes out the
    same size in every row. `panel_key` picks that geometry out of the config;
    `narrow_panel` is the figure whose panels carry one bar rather than a
    scenario axis.

    A row holding one group is headed at the figure's left margin; a packed row
    names each of its groups over that group's first panel instead. Those headers
    are kept out of the layout, or a long group name would push the panel beside
    it away and the gaps would stop being even. Returns the figure, the axes keyed
    by member, and the headers — artists `save_figure` has to be told about
    explicitly, since they sit outside the axes.
    """
    panel = plotting[panel_key]
    ink = plotting["ink"]
    gap = panel["group_gap"]
    rows = pack_rows(groups, panel["max_columns"])

    ncols = max(sum(len(m) for _, m in row) for row in rows)
    budget = ncols + gap * max(len(row) - 1 for row in rows)

    fig = plt.figure(
        figsize=(panel["width"] * budget, panel["height"] * len(rows)),
        layout="constrained",
    )
    subfigs = np.atleast_1d(fig.subfigures(len(rows), 1))

    axes: dict[str, plt.Axes] = {}
    headers = []
    for subfig, row in zip(subfigs, rows):
        # Column widths: a spacer before every group but the first, then whatever
        # of the shared budget this row did not use, kept as a trailing spacer.
        widths, is_panel = [], []
        for index, (_, members) in enumerate(row):
            if index:
                widths.append(gap)
                is_panel.append(False)
            widths.extend([1.0] * len(members))
            is_panel.extend([True] * len(members))
        if budget - sum(widths) > 1e-9:
            widths.append(budget - sum(widths))
            is_panel.append(False)

        cells = subfig.subplots(
            1, len(widths), squeeze=False, gridspec_kw={"width_ratios": widths}
        )[0]
        for cell, drawn in zip(cells, is_panel):
            if not drawn:
                cell.set_visible(False)
        panels = [cell for cell, drawn in zip(cells, is_panel) if drawn]

        # A packed row's headers are annotations kept out of the layout, so
        # nothing reserves the strip they sit in and they would land on the row
        # above. An empty suptitle reserves exactly one line of it, once, and the
        # headers align because each is the same offset above its own panel.
        if len(row) > 1:
            subfig.suptitle(" ")

        column = 0
        for group, members in row:
            for offset, member in enumerate(members):
                axes[member] = panels[column + offset]
            headers.append(
                subfig.suptitle(group, x=0.0, ha="left", color=ink["primary"])
                if len(row) == 1
                else panels[column].annotate(
                    group,
                    xy=(0.0, 1.0),
                    xytext=(0.0, 30.0),
                    xycoords="axes fraction",
                    textcoords="offset points",
                    ha="left",
                    va="bottom",
                    # Matched to the suptitle a single-group row uses, so a
                    # heading looks the same however its row came out.
                    fontsize=mpl.rcParams["figure.titlesize"],
                    fontweight=mpl.rcParams["figure.titleweight"],
                    color=ink["primary"],
                    annotation_clip=False,
                    in_layout=False,
                )
            )
            column += len(members)
    return fig, axes, headers


def flow_rows(
    groups: dict[str, list[str]], columns: int
) -> list[list[tuple[str, list[str]]]]:
    """`groups` flowed across rows of `columns` panels, splitting where a row fills.

    `pack_rows` keeps a group whole and gives it a row of its own, which costs a
    row per group however few panels it holds. This packs the panels instead and
    lets a group run on to the next row, so what a row holds is however many
    panels fit. Each row comes back as the runs of one group it holds, in order,
    which is what the band over the panels is drawn from.
    """
    rows: list[list[tuple[str, list[str]]]] = []
    row: list[tuple[str, list[str]]] = []
    width = 0
    for group, members in groups.items():
        remaining = list(members)
        while remaining:
            run, remaining = remaining[: columns - width], remaining[columns - width :]
            row.append((group, run))
            width += len(run)
            if width == columns:
                rows.append(row)
                row, width = [], 0
    if row:
        rows.append(row)
    return rows


def flow_panel_grid(
    groups: dict[str, list[str]],
    bars: dict[str, float],
    labels: dict[str, str],
    colors: dict[str, str],
    group_names: dict[str, str],
    plotting: dict,
    panel_key: str = "metal_panel",
    value_label: str | None = None,
) -> tuple[plt.Figure, dict[str, plt.Axes], list]:
    """A panel per group member, flowed across the rows, the bars named once each.

    Every panel carries the same bars, so their names are drawn once per row in a
    column of its own rather than on all of them: an axes holding nothing but the
    names, on the same scale as the panels beside it. That is what pays for the
    bars being horizontal — a name has the width of the whole column, so the
    scenarios can be read straight down instead of slanted under every panel.

    A group is a run of panels rather than a row of its own: the rows are filled
    to `max_columns` whatever the groups do, and the group is said on the panels
    instead, as a band over its run in the hue `colors` gives it, named by
    `group_names`, and a wider spacer where one run ends and the next begins. A
    run continued on the next row is banded again, since a band names the run
    under it.

    The figure has a page to fit, so it is sized inwards rather than outwards:
    `width` is the page, the panels get what the name column and the spacers
    leave, and a row is the bar axis at `bar_pitch` an inch a bar plus
    `row_chrome` for the names over and under it. Every row reserves the same
    spacers as the row that needs the most, so a panel is the same width in all
    of them.

    Returns the figure, the panels keyed by member, and the bands — artists
    outside the axes, which `save_figure` has to be told about explicitly.
    """
    panel = plotting[panel_key]
    ink = plotting["ink"]
    band = panel["band"]
    rows = flow_rows(groups, panel["max_columns"])
    low, high = category_limits(bars, plotting, panel_key)

    # Panels are the width the page has left once the names and the spacers are
    # taken out, counted against the row that spends the most on spacers.
    boundaries = max(len(row) - 1 for row in rows)
    reserved = (
        panel["label_width"]
        + panel["panel_gap"] * (panel["max_columns"] - 1)
        + panel["boundary_gap"] * boundaries
    )
    panel_width = (panel["width"] - reserved) / panel["max_columns"]
    if panel_width <= 0.0:
        raise ValueError(
            f"{panel_key}.width of {panel['width']} in leaves nothing for "
            f"{panel['max_columns']} panels once {reserved:.2f} in of names and "
            "spacers are taken out"
        )

    row_height = (high - low) * panel["bar_pitch"] + panel["row_chrome"]
    fig = plt.figure(
        figsize=(panel["width"], row_height * len(rows)), layout="constrained"
    )
    # Across a row the spacers are the spacing, in full: constrained layout's own
    # padding would add to them unevenly, since a row's first panel is the only
    # one whose axis carries names. Between rows it is the only spacing there is
    # — a row's panels take whatever height its names leave, so `row_gap` is what
    # separates one row's numbers from the next row's metals.
    fig.get_layout_engine().set(
        w_pad=0.0, h_pad=panel["row_gap"], wspace=0.0, hspace=0.0
    )
    subfigs = np.atleast_1d(fig.subfigures(len(rows), 1))

    axes: dict[str, plt.Axes] = {}
    bands = []
    for subfig, row in zip(subfigs, rows):
        # Column widths in inches: the name column, a panel per member, and a
        # spacer between every two of them — wider at a group boundary, which is
        # what keeps the runs apart without giving each one a row.
        widths, kinds = [panel["label_width"]], ["names"]
        for index, (_, members) in enumerate(row):
            for offset, _ in enumerate(members):
                if index or offset:
                    boundary = panel["boundary_gap"] if not offset else 0.0
                    widths.append(panel["panel_gap"] + boundary)
                    kinds.append("gap")
                widths.append(panel_width)
                kinds.append("panel")
        trailing = panel["width"] - sum(widths)
        if trailing > 1e-9:
            widths.append(trailing)
            kinds.append("gap")

        cells = subfig.subplots(
            1, len(widths), squeeze=False, gridspec_kw={"width_ratios": widths}
        )[0]
        for cell, kind in zip(cells, kinds):
            if kind == "gap":
                cell.set_visible(False)
        panels = [cell for cell, kind in zip(cells, kinds) if kind == "panel"]

        # The name column: no data, no axis, the bars' own scale, and every name
        # against its right edge so it reads as the first panel's axis.
        names = cells[0]
        names.set_ylim(high, low)
        names.set_xlim(0.0, 1.0)
        names.set_axis_off()
        for key, position in bars.items():
            names.annotate(
                labels[key],
                xy=(1.0, position),
                xytext=(-4.0, 0.0),
                textcoords="offset points",
                ha="right",
                va="center",
                fontsize=panel["label_size"],
                color=ink["secondary"],
            )

        column = 0
        for group, members in row:
            for offset, member in enumerate(members):
                ax = panels[column + offset]
                axes[member] = ax
                # A rule over each panel of the run rather than one across all of
                # them: an artist may only live in one axes, and the spacers the
                # runs are already separated by are what break it where it should
                # break.
                bands.extend(band_rule(ax, subfig, colors[group], band))
            bands.append(
                band_name(panels[column], group_names[group], colors[group], band)
            )
            column += len(members)

    if value_label is not None:
        # Every panel is on its own scale, so the unit is the only thing they
        # share and it is said once for the figure.
        fig.supxlabel(
            value_label,
            color=ink["secondary"],
            fontsize=mpl.rcParams["axes.labelsize"],
        )
    return fig, axes, bands


def band_rule(ax, fig, color: str, band: dict) -> list:
    """The rule of a group band, `band["pad"]` points over `ax`.

    Out of the layout, like the band's name: `band_title_pad` reserves the strip.
    """
    above = mtransforms.offset_copy(ax.transAxes, fig=fig, y=band["pad"], units="points")
    return ax.plot(
        [0.0, 1.0], [1.0, 1.0], transform=above, color=color,
        linewidth=band["width"], solid_capstyle="butt", clip_on=False,
        in_layout=False,
    )


def band_name(ax, name: str, color: str, band: dict):
    """The name of a group band, over its rule from the left edge of `ax`."""
    return ax.annotate(
        name,
        xy=(0.0, 1.0),
        xytext=(0.0, band["pad"] + 3.0),
        xycoords="axes fraction",
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=band["size"],
        fontweight="bold",
        color=color,
        annotation_clip=False,
        in_layout=False,
    )


def pie_block_grid(
    blocks: dict[str, int], plotting: dict, panel_key: str = "market_share"
) -> tuple[plt.Figure, dict[str, tuple[plt.Axes, list[plt.Axes]]]]:
    """A block per key: a name column, then `blocks[key]` pie axes side by side.

    Blocks are placed first-fit in order on rows the page wide, so a block too
    wide for the row it would end starts the next one, and a narrower block after
    it can still fill the gap it left. Every pie column is `pie_width` and every
    name column `legend_width` inches, so a pie is one size wherever it lands.
    Returns the figure and, per key, its name column and its pies.
    """
    spec = plotting[panel_key]
    rows: list[list[str]] = []
    room: list[float] = []
    for key, count in blocks.items():
        width = spec["legend_width"] + count * spec["pie_width"]
        if width > spec["width"]:
            raise ValueError(
                f"block {key!r} of {count} pies is {width:.2f} in, wider than the "
                f"{spec['width']} in of {panel_key}.width"
            )
        for index, left in enumerate(room):
            if width + spec["block_gap"] <= left + 1e-9:
                rows[index].append(key)
                room[index] -= width + spec["block_gap"]
                break
        else:
            rows.append([key])
            room.append(spec["width"] - width)

    fig = plt.figure(
        figsize=(spec["width"], spec["row_height"] * len(rows)), layout="constrained"
    )
    # The column widths are the spacing, as in `flow_panel_grid`.
    fig.get_layout_engine().set(
        w_pad=0.0, h_pad=spec["row_gap"], wspace=0.0, hspace=0.0
    )
    cells: dict[str, tuple[plt.Axes, list[plt.Axes]]] = {}
    for subfig, row in zip(np.atleast_1d(fig.subfigures(len(rows), 1)), rows):
        widths, owners = [], []
        for index, key in enumerate(row):
            if index:
                widths.append(spec["block_gap"])
                owners.append(None)
            widths.extend([spec["legend_width"], *[spec["pie_width"]] * blocks[key]])
            owners.extend([key] * (1 + blocks[key]))
        trailing = spec["width"] - sum(widths)
        if trailing > 1e-9:
            widths.append(trailing)
            owners.append(None)

        axes = subfig.subplots(
            1, len(widths), squeeze=False, gridspec_kw={"width_ratios": widths}
        )[0]
        for ax, owner in zip(axes, owners):
            if owner is None:
                ax.set_visible(False)
            else:
                ax.set_axis_off()
        for key in row:
            names, *pies = [ax for ax, owner in zip(axes, owners) if owner == key]
            cells[key] = (names, pies)
    return fig, cells


def share_pie(ax, shares: pd.Series, colors: dict[str, str], plotting: dict) -> None:
    """`shares` clockwise from twelve o'clock in index order, a zero share drawn
    as nothing rather than as a hairline wedge."""
    drawn = shares[shares > 0]
    bar = plotting["bar"]
    ax.pie(
        drawn, colors=[colors[key] for key in drawn.index], startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": bar["edge_color"], "linewidth": bar["edge_width"]},
    )


def name_column_legend(ax, handles: list, plotting: dict, panel_key: str):
    """A legend standing in for a name column: the names against the right edge
    of `ax`, each swatch between its name and the panel it keys."""
    spec = plotting[panel_key]
    legend = ax.legend(
        handles=handles, loc="center right", bbox_to_anchor=(1.0, 0.5),
        markerfirst=False, frameon=False, borderaxespad=0.0, borderpad=0.0,
        fontsize=spec["label_size"], labelcolor=plotting["ink"]["secondary"],
        labelspacing=0.35, handlelength=1.0, handletextpad=0.5,
    )
    # Sized by the column it sits in, not a claim on the layout.
    legend.set_in_layout(False)
    return legend


def band_title_pad(plotting: dict, panel_key: str) -> float:
    """The room a panel's title has to leave under itself for the group band.

    `flow_panel_grid` draws the band between the panel and its title, and out of
    the layout — a group name is wider than the panel it starts over, and in the
    layout it would push the panel beside it away. Nothing then reserves the
    strip it sits in, so the title does, by being pushed up by this much: pass it
    to `style_panel` as `extra_pad`. Reserving it is not cosmetic, since the
    strip a band is drawn in otherwise belongs to the row above.
    """
    band = plotting[panel_key]["band"]
    return band["pad"] + band["size"] + 2.0


def compact_ticks(ax, plotting: dict, panel_key: str, orientation: str) -> None:
    """The value axis of a small panel: few ticks, and short names for them.

    A panel an inch wide has room for `value_ticks` numbers and no more, and the
    quantities here run from grams of iridium to megatonnes of aluminium, so a
    tick is named as briefly as its own size allows rather than on one format.
    """
    _, value = bar_axes(orientation)
    axis = getattr(ax, f"{value}axis")
    # MaxNLocator counts intervals, the config counts the numbers they carry.
    axis.set_major_locator(mticker.MaxNLocator(plotting[panel_key]["value_ticks"] - 1))
    axis.set_major_formatter(mticker.FuncFormatter(_short_number))


def _short_number(value: float, _position=None) -> str:
    """A number in as few characters as it can be told apart in."""
    if value == 0.0:
        return "0"
    if abs(value) >= 1e3:
        return f"{value / 1e3:g}k"
    if abs(value) >= 1.0:
        return f"{value:g}"
    return f"{value:.2g}"


def panel_title(
    ax,
    plotting: dict,
    title: str | None,
    subtitle: str | None,
    extra_pad: float = 0.0,
    style: dict | None = None,
    loc: str = "left",
) -> None:
    """A left-aligned title with an optional muted second line under it.

    `loc` of "center" centres it over the panel instead, for a panel whose title
    is nearly as wide as it is: left-aligned, a long name spills the whole of its
    overhang onto the panel to its right, and centred it spills half of it into
    the space either side. The subtitle stays at the panel's left edge, since a
    figure that needs one has the room for it.

    `extra_pad` reserves room above the subtitle for anything else the caller
    puts over the axes — column-group headers, say — which would otherwise be
    printed straight through it.

    `style` is Text keywords for the title itself, so a panel too small for a
    second line can say in how its name is written what the subtitle would have
    said — the encoding `category_axis`'s `label_styles` carries on a bar.

    A `title` of None leaves the space over the axes empty, for a figure whose
    caption is written where it is published rather than on the figure.
    """
    ink = plotting["ink"]
    if title is None:
        if subtitle is not None:
            raise ValueError("a subtitle with no title has nothing to sit under")
        return
    # The subtitle sits in the title's padding, so the pad has to clear it.
    # set_title keeps a Text per `loc`, so the one to style is the one it wrote
    # to rather than ax.title, which is the centred one whatever `loc` says.
    drawn = ax.set_title(
        title, loc=loc, fontsize=9.5, color=ink["primary"],
        pad=(SUBTITLE_PAD if subtitle is not None else TITLE_PAD) + extra_pad,
    )
    if style is not None:
        drawn.set(**style)
    if subtitle is not None:
        ax.annotate(
            subtitle,
            xy=(0.0, 1.0),
            xytext=(0.0, 3.0),
            xycoords="axes fraction",
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=7.5,
            color=ink["muted"],
            # Out of the layout for the same reason as the group header: a wide
            # subtitle would otherwise push the panel next to it away.
            in_layout=False,
        )


def style_panel(
    ax,
    plotting: dict,
    *,
    title: str | None,
    ylabel: str,
    subtitle: str | None = None,
    log: bool = False,
    orientation: str = "vertical",
    title_style: dict | None = None,
    title_loc: str = "left",
    extra_pad: float = 0.0,
    label_loc: str = "center",
) -> None:
    """Strip a panel back to its data: two spines, a recessive grid down the
    value axis, a left-aligned title with an optional muted second line under it.

    `ylabel` names the value axis, which is x where the bars are horizontal;
    `orientation` is the bars', and moves the grid and the log scale with them.
    `label_loc` aligns that name to the axis, for a name wider than its panel.
    """
    ink = plotting["ink"]
    _, value = bar_axes(orientation)
    panel_title(
        ax, plotting, title, subtitle,
        extra_pad=extra_pad, style=title_style, loc=title_loc,
    )
    getattr(ax, f"set_{value}label")(ylabel, color=ink["secondary"], loc=label_loc)
    if log:
        getattr(ax, f"set_{value}scale")("log")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(ink["muted"])
    ax.tick_params(colors=ink["secondary"], which="both")
    ax.grid(axis=value, color=ink["grid"], linewidth=0.6, which="major")
    ax.set_axisbelow(True)


def decade_axis(ax, values, orientation: str = "vertical") -> None:
    """Snap a log value axis out to whole decades and label the decades alone.

    An axis spanning under a decade otherwise labels its minor ticks as well, and
    at a panel's width those run into one another. The lower end sits at least
    half a decade below the smallest value, so its bar is still drawn.
    """
    values = np.asarray(values, dtype=float)
    if (values <= 0).any():
        raise ValueError("a log axis cannot carry zero or negative values")
    exponents = np.log10(values)
    _, value = bar_axes(orientation)
    getattr(ax, f"set_{value}lim")(
        10.0 ** np.floor(exponents.min() - 0.5), 10.0 ** np.ceil(exponents.max())
    )
    axis = getattr(ax, f"{value}axis")
    axis.set_major_locator(mticker.LogLocator(base=10))
    axis.set_minor_formatter(mticker.NullFormatter())


def category_axis(
    ax,
    positions: dict[str, float],
    labels: dict[str, str] | None,
    plotting: dict,
    panel_key: str = "panel",
    label_styles: dict[str, dict] | None = None,
    orientation: str = "vertical",
) -> None:
    """Tick and label the bar axis at `positions`, with half a bar of margin.

    `label_rotation` is the panel spec's, because it is a consequence of how much
    room a bar has: 45 degrees where a bar is wide, upright where it is not.
    Upright is also what a figure naming its groups under the axis needs — a
    slanted label drifts left of the bar it belongs to as it descends, and by the
    bottom of a long name it is over a different group.

    Horizontal bars run down the axis in the order `positions` gives them: the
    first bar is at the top.

    `labels` of None ticks the axis without naming it, for a panel whose bars are
    named once for a whole row of panels somewhere else (`flow_panel_grid`).

    `label_styles` sets individual labels apart from the rest — a dict per key of
    keyword arguments for its Text, so an axis can carry a second, quieter
    encoding in the way a name is written rather than in another mark.
    """
    keys = list(positions)
    rotation = plotting[panel_key]["label_rotation"]
    upright = bar_axes(orientation) == ("x", "y")
    ticks = [positions[key] for key in keys]
    names = [""] * len(keys) if labels is None else [labels[key] for key in keys]
    low, high = category_limits(positions, plotting, panel_key)
    if upright:
        ax.set_xticks(
            ticks,
            names,
            rotation=rotation,
            # A slanted label hangs off the tick; an upright or level one is centred.
            ha="right" if rotation % 90 else "center",
            color=plotting["ink"]["secondary"],
        )
        ax.set_xlim(low, high)
    else:
        ax.set_yticks(
            ticks, names, rotation=rotation, ha="right", va="center",
            color=plotting["ink"]["secondary"],
        )
        # Reversed, so the bars read top-down in the order they are given.
        ax.set_ylim(high, low)
    if label_styles is not None:
        text_of = ax.get_xticklabels if upright else ax.get_yticklabels
        for key, text in zip(keys, text_of()):
            text.set(**label_styles[key])


def _wrap_to_width(text: str, characters: int) -> str:
    """`text` broken into lines of at most `characters`, at spaces and slashes.

    A group name is written under a block of bars two or three bars wide, so it
    is usually wider than the block it names and has to wrap or collide with the
    next one. Breaking after a slash as well as at a space is what lets
    "Solar/semiconductor" and "H2/PGM catalysts" wrap at all. A chunk longer than the
    allowance is kept whole rather than cut mid-word.
    """
    chunks = [chunk for chunk in re.split(r"(?<=[/ ])", text) if chunk]
    lines = [""]
    for chunk in chunks:
        if lines[-1] and len(lines[-1].rstrip()) + len(chunk) > characters:
            lines.append("")
        lines[-1] += chunk
    return "\n".join(line.rstrip() for line in lines)


def _axis_label_reach(ax, upright: bool) -> float:
    """How far the tick labels on the category axis reach past it, in points.

    Measured off the Texts, so a name set bold by `label_styles` counts at the
    width it is really set to and the rotation decides which of its dimensions
    crosses the axis. `_TEXT_METRICS` needs no renderer, so no draw is forced.
    """
    texts = ax.get_xticklabels() if upright else ax.get_yticklabels()
    reach = 0.0
    for text in texts:
        name = text.get_text()
        if not name:
            continue
        width, height, _ = _TEXT_METRICS.get_text_width_height_descent(
            name, text.get_fontproperties(), ismath=False
        )
        angle = np.radians(text.get_rotation())
        sideways = abs(width * np.sin(angle)) + abs(height * np.cos(angle))
        lengthways = abs(width * np.cos(angle)) + abs(height * np.sin(angle))
        reach = max(reach, sideways if upright else lengthways)
    return reach


def group_axis(
    ax,
    positions: dict[str, float],
    groups: dict[str, list[str]],
    names: dict[str, str],
    plotting: dict,
    panel_key: str = "panel",
    orientation: str = "vertical",
) -> list:
    """Name each group of bars beyond the category axis, over a rule spanning its
    members.

    The gap `bar_positions` leaves between two groups is what separates them on
    the axis; this says what the blocks it makes are. The rule clears the bar names
    `category_axis` has written — ticks, pad and the longest name as it will be set
    (`_axis_label_reach`) — by `group_rule_gap` points, with `group_name_gap` more
    between it and the name it carries. Both gaps are blank space and nothing else,
    so renaming a bar moves the rule instead of crowding it.

    `names` is what each group is called, as `category_axis` takes `labels`.
    `orientation` is the bars': under the axis where they stand up, left of it and
    turned on their side where they lie down, as the names beside them are.

    The name is wrapped to the extent of its own block, so a wide name stacks
    across a narrow block instead of running into the block beside it. Measuring
    that extent needs the limits, so `category_axis` has to have run first.

    The names sit outside the axes, so they are returned for `save_figure`'s
    `extra_artists`: passing that argument at all replaces matplotlib's own
    collection, and a name left out of it is cropped away.
    """
    panel = plotting[panel_key]
    ink = plotting["ink"]
    category, _ = bar_axes(orientation)
    upright = category == "x"
    size = mpl.rcParams[f"{category}tick.labelsize"]
    half = panel["bar_width"] / 2
    # Category axis in data, value axis in axes fraction, offset clear of the panel.
    pad = (
        mpl.rcParams[f"{category}tick.major.size"]
        + mpl.rcParams[f"{category}tick.major.pad"]
        + _axis_label_reach(ax, upright)
        + panel["group_rule_gap"]
    )
    beyond = mtransforms.offset_copy(
        ax.get_xaxis_transform() if upright else ax.get_yaxis_transform(),
        fig=ax.figure,
        units="points",
        **({"y": -pad} if upright else {"x": -pad}),
    )
    # What a name may occupy: its own block, plus the blank gap either side of
    # it, which belongs to the boundary and holds nothing else. In points, on the
    # same rough-but-consistent glyph estimate label_points uses; constrained
    # layout has not run, so this follows the axes' current position rather than
    # its final one.
    gap = plotting["bar"]["group_gap"]
    blocks = {}
    for group, members in groups.items():
        span = [positions[member] for member in members if member in positions]
        if not span:
            continue
        start, end = min(span) - half, max(span) + half
        ends = [start - gap / 2, end + gap / 2]
        room = ax.transData.transform(
            [(at, 0.0) for at in ends] if upright else [(0.0, at) for at in ends]
        )
        # Absolute: a horizontal bar axis runs top-down.
        width = abs(np.diff(room[:, 0 if upright else 1])[0]) * 72.0 / ax.figure.dpi
        wrapped = _wrap_to_width(names[group], max(1, int(width / (0.58 * size))))
        blocks[group] = (start, end, width, wrapped)

    # One size for every name, set by the name that fits worst: a name too wide
    # for its block even wrapped — a single long word over a one-bar block — is
    # what decides it, down to `group_label_floor`. Sizing each name to its own
    # block instead would make the type size read as if it meant something.
    fitted = min(
        size * width / (0.58 * size * max(len(line) for line in wrapped.split("\n")))
        for _, _, width, wrapped in blocks.values()
    )
    fitted = max(panel["group_label_floor"], min(size, fitted))

    names = []
    for group, (start, end, _, wrapped) in blocks.items():
        along, across = [start, end], [0.0, 0.0]
        middle = 0.5 * (start + end)
        ax.plot(
            *((along, across) if upright else (across, along)),
            transform=beyond,
            color=ink["muted"],
            linewidth=0.8,
            solid_capstyle="butt",
            clip_on=False,
        )
        names.append(ax.annotate(
            wrapped,
            xy=(middle, 0.0) if upright else (0.0, middle),
            xycoords=beyond,
            xytext=(
                (0.0, -panel["group_name_gap"])
                if upright
                else (-panel["group_name_gap"], 0.0)
            ),
            textcoords="offset points",
            ha="center" if upright else "right",
            va="top" if upright else "center",
            # Turned with its bars, so a wrapped name stacks away from the panel
            # and reads the way the names beside it do.
            rotation=0 if upright else 90,
            fontsize=fitted,
            fontweight="bold",
            color=ink["primary"],
            linespacing=1.1,
            annotation_clip=False,
        ))
    return names


def overrun_marks(
    ax,
    positions: dict[str, float],
    totals: pd.Series,
    cap: float,
    overrun: dict,
    plotting: dict,
    panel_key: str = "panel",
    orientation: str = "vertical",
) -> tuple[list[str], list]:
    """Mark every bar the axis cap cuts with an arrow head and its true length.

    One shared linear axis is what makes the bars comparable, and fitting it to
    the few longest flattens every other bar to nothing. Capping keeps the
    resolution where the small bars are and cuts the long ones instead; the arrow
    says a bar is cut and the number says where it reaches, so the cap hides
    nothing.

    Both marks sit beside the bar rather than on it — `offset_bars` along the
    category axis, at the end of the value axis — so the cut bar stays readable
    for its whole length. `orientation` is the bars': the arrow points the way
    they grow.

    Returns the keys that were cut, and the marks that say so. Those sit past the
    end of the axis, so they go to `save_figure`'s `extra_artists`: passing that
    argument at all replaces matplotlib's own collection, and a mark left out of
    it is cropped away.
    """
    offset = overrun["offset_bars"] * plotting[panel_key]["bar_width"]
    upright = bar_axes(orientation) == ("x", "y")
    cut = [key for key in positions if totals[key] > cap]
    marks = []
    for key in cut:
        at = positions[key] + offset
        point = (at, cap) if upright else (cap, at)
        marks += ax.plot(
            *point,
            marker=_overrun_marker(orientation),
            color=overrun["color"],
            markersize=overrun["marker_size"],
            clip_on=False,
            zorder=6,
        )
        marks.append(ax.annotate(
            overrun["format"].format(totals[key]),
            xy=point,
            xytext=(
                (0.0, overrun["label_offset"])
                if upright
                else (overrun["label_offset"], 0.0)
            ),
            textcoords="offset points",
            ha="center" if upright else "left",
            va="bottom" if upright else "center",
            fontsize=overrun["label_size"],
            color=overrun["color"],
            annotation_clip=False,
            zorder=6,
        ))
    return cut, marks


def _overrun_marker(orientation: str) -> str:
    """The arrow head `overrun_marks` draws, pointing the way the bars grow."""
    return "^" if bar_axes(orientation) == ("x", "y") else ">"


def overrun_key(ax, overrun: dict, plotting: dict, orientation: str = "vertical"):
    """`overrun_marks`' arrow named inside the panel, its lower right corner at
    `overrun.key_anchor` in axes fractions.

    It is drawn on the surface colour, so a grid line behind it does not strike
    the name through.
    """
    return ax.legend(
        handles=[
            mlines.Line2D(
                [], [], color=overrun["color"], marker=_overrun_marker(orientation),
                linestyle="none", markersize=overrun["marker_size"],
                label=overrun["legend_label"],
            )
        ],
        loc="lower right", bbox_to_anchor=overrun["key_anchor"], borderaxespad=0.0,
        facecolor=plotting["ink"]["surface"], edgecolor="none", framealpha=1.0,
        borderpad=0.3, handlelength=1.0,
    )


def style_scatter(
    ax,
    plotting: dict,
    *,
    title: str | None,
    xlabel: str,
    ylabel: str,
    subtitle: str | None = None,
    log_y: bool = False,
    symlog_y: float | None = None,
) -> None:
    """style_panel for a scatter: both axes carry a grid, since a point is read
    off both of them rather than off a baseline.

    `symlog_y` is the alternative to `log_y` for an axis that spans orders of
    magnitude but has to reach zero, or below it: the axis is linear within
    `symlog_y` of zero and logarithmic outside it.
    """
    if log_y and symlog_y is not None:
        raise ValueError("an axis is either log or symlog, not both")
    style_panel(
        ax, plotting, title=title, ylabel=ylabel, subtitle=subtitle, log=log_y
    )
    if symlog_y is not None:
        ax.set_yscale("symlog", linthresh=symlog_y)
    ax.set_xlabel(xlabel, color=plotting["ink"]["secondary"])
    ax.grid(axis="x", color=plotting["ink"]["grid"], linewidth=0.6, which="major")


def stand_y_axis_at(ax, plotting: dict, x: float) -> None:
    """Draw the vertical axis at data `x` rather than at the panel's left edge.

    A panel whose x limits run wider than its data — the margin `label_points`
    needs to put a crowded name to the *left* of its marker — otherwise puts its
    heaviest vertical line where the data does not begin. The spine keeps the
    ticks and their names at the edge but drops to the grid's own hue, so the
    limit reads as the edge of the panel rather than as the start of the scale.
    """
    ink = plotting["ink"]
    ax.spines["left"].set_color(ink["grid"])
    ax.axvline(
        x,
        color=ink["muted"],
        linewidth=mpl.rcParams["axes.linewidth"],
        # Over the gridline it stands in for, under the data it measures.
        zorder=0.6,
    )


TRACE_ENDS = ("base", "reduced")


def marker_fill(filled: bool, color: str, ink: dict) -> dict:
    """scatter's face and edge for a marker that is filled with `color`, or open.

    The two are the same mark seen from either side: a filled one is the colour
    with the page's own hairline around it, an open one the page with the colour
    around it. The fill is what says which end of a trace a point is, so
    `open_marker_size` draws the two to the same extent.
    """
    return (
        {"facecolors": color, "edgecolors": ink["surface"]}
        if filled
        else {"facecolors": ink["surface"], "edgecolors": color}
    )


def open_marker_size(size: float, edge_width: float, outline_width: float) -> float:
    """The `s` of an open marker whose ring reaches as far as the colour of a
    filled one of area `size`.

    An edge is stroked centred on the marker's path, so the filled marker's
    page-coloured hairline takes half its width off the fill all round, and the
    open marker's ring reaches half its width beyond the path.
    """
    return (np.sqrt(size) - edge_width - outline_width) ** 2


def traced_points(
    ax,
    frame: pd.DataFrame,
    colors: dict[str, str],
    markers: dict[str, str],
    trace: dict,
    ink: dict,
    filled_end: str = "base",
    size_scales: dict[str, float] | None = None,
    outline_scales: dict[str, float] | None = None,
) -> None:
    """One arrow per row of `frame`, from where a thing sits to where it can get to.

    `frame` is indexed by the key that `colors` and `markers` are keyed by, with
    columns `x`, `y`, `x_to`, `y_to`. One end is a filled marker and the other an
    open one of the same shape, so the direction reads off the marker fill
    without following the arrow. `filled_end` says which: fill the `base` end to
    draw a figure about where things are, the `reduced` end to draw one about
    where they can get to. The filled end is also the one drawn on top.

    A trace shorter than `minimum_visible` of the drawn x range keeps its arrow
    but drops the reduced marker, which would otherwise overprint the base one
    into a smudge — so a thing that does not move is left showing the base
    marker, whichever way round the fill is.

    Both ends reach the same extent: `trace.size` is the filled marker's area,
    and the open one is drawn smaller, so its ring ends where the fill does.

    `size_scales` multiplies that area per key, so shapes covering different
    areas at one `s` draw the same size. `outline_scales` multiplies
    `edge_width` on the open end alone, for a key drawn heavier than the rest:
    the filled end's outline is the page's own hairline, and thickening it would
    eat the fill.
    """
    if filled_end not in TRACE_ENDS:
        raise ValueError(f"filled_end is {filled_end!r}; expected one of {TRACE_ENDS}")
    span = ax.get_xlim()[1] - ax.get_xlim()[0]
    for key, row in frame.iterrows():
        color = colors[key]
        size = trace["size"] * (1.0 if size_scales is None else size_scales[key])
        outline = trace["edge_width"] * (1.0 if outline_scales is None else outline_scales[key])
        filled = {"s": size, "linewidths": trace["edge_width"]}
        hollow = {"s": open_marker_size(size, trace["edge_width"], outline), "linewidths": outline}
        moved = abs(row["x_to"] - row["x"]) > trace["minimum_visible"] * span
        ax.annotate(
            "",
            xy=(row["x_to"], row["y_to"]),
            xytext=(row["x"], row["y"]),
            arrowprops={
                "arrowstyle": "-|>",
                "color": color,
                "alpha": trace["alpha"],
                "linewidth": trace["line_width"],
                "shrinkA": 3.0,
                "shrinkB": 1.0,
            },
            zorder=2,
        )
        if moved:
            ax.scatter(
                row["x_to"], row["y_to"], marker=markers[key],
                **(filled if filled_end == "reduced" else hollow),
                **marker_fill(filled_end == "reduced", color, ink),
                zorder=4 if filled_end == "reduced" else 3,
            )
        ax.scatter(
            row["x"], row["y"], marker=markers[key],
            **(filled if filled_end == "base" else hollow),
            **marker_fill(filled_end == "base", color, ink),
            zorder=4 if filled_end == "base" else 3,
        )


def trace_handle(
    label: str,
    marker: str,
    filled: bool,
    trace: dict,
    ink: dict,
    size_scale: float = 1.0,
    outline_scale: float = 1.0,
):
    """A legend entry drawn as traced_points draws one end of a trace, in neutral
    ink, so the key and the panel agree on fill, size and outline."""
    fill = marker_fill(filled, ink["secondary"], ink)
    size = size_scale * trace["size"]
    outline = trace["edge_width"] * (1.0 if filled else outline_scale)
    return mlines.Line2D(
        [], [],
        linestyle="none",
        marker=marker,
        # `s` is an area and Line2D's markersize a diameter.
        markersize=np.sqrt(
            size if filled else open_marker_size(size, trace["edge_width"], outline)
        ),
        markerfacecolor=fill["facecolors"],
        markeredgecolor=fill["edgecolors"],
        markeredgewidth=outline,
        label=label,
    )


def plain_points(
    ax,
    frame: pd.DataFrame,
    colors: dict[str, str],
    markers: dict[str, str],
    size: float,
    ink: dict,
) -> None:
    """One marker per row of `frame` (columns `x`, `y`), keyed by its index.

    traced_points for a scatter whose points do not move: the same colour and
    shape encoding, no arrow.
    """
    for key, row in frame.iterrows():
        ax.scatter(
            row["x"], row["y"],
            s=size, marker=markers[key],
            **marker_fill(True, colors[key], ink),
            linewidths=1.0, zorder=4,
        )


def range_whiskers(
    ax,
    positions: dict[str, float],
    low: pd.Series,
    high: pd.Series,
    whisker: dict,
    cap: float | None = None,
) -> list[str]:
    """A capped vertical span per entry of `positions`, drawn over the bars.

    `low` and `high` are indexed by the same keys. A span is what a bar cannot
    say: the bar is one scenario, the whisker is every scenario.

    One span running orders of magnitude past the rest would flatten every other
    bar on a shared linear axis, so `cap` cuts it at the axis top and marks it
    with an arrow and where it really reaches. Returns the keys that were cut, so
    the caller can say so out loud.
    """
    keys = [key for key in positions if key in low.index]
    x = np.array([positions[key] for key in keys])
    bottom, top = low[keys].to_numpy(), high[keys].to_numpy()
    overrun = top > cap if cap is not None else np.zeros(len(keys), dtype=bool)
    drawn = np.minimum(top, cap) if cap is not None else top

    half = whisker["cap_width"] / 2
    ax.vlines(
        x, bottom, drawn,
        color=whisker["color"], linewidth=whisker["line_width"],
        alpha=whisker["alpha"], zorder=5,
    )
    # Only the ends that are real ends get a bar across them; a cut one gets an
    # arrow head instead, so the two cannot be confused.
    ends = np.concatenate([bottom, drawn[~overrun]])
    at = np.concatenate([x, x[~overrun]])
    ax.hlines(
        ends, at - half, at + half,
        color=whisker["color"], linewidth=whisker["line_width"],
        alpha=whisker["alpha"], zorder=5,
    )
    for index in np.flatnonzero(overrun):
        ax.plot(
            x[index], drawn[index],
            marker="^", color=whisker["color"], markersize=4.5,
            alpha=whisker["alpha"], zorder=5, clip_on=False,
        )
        # Below the head and to the side, so the label stays inside the panel:
        # above it would collide with whatever sits over the axis.
        ax.annotate(
            whisker["overrun_format"].format(top[index]),
            xy=(x[index], drawn[index]),
            xytext=(4.5, -3.0),
            textcoords="offset points",
            ha="left", va="top",
            fontsize=7.0, color=whisker["color"],
        )
    return [keys[index] for index in np.flatnonzero(overrun)]


def diverging_scale(heatmap: dict):
    """The colourmap and norm a signed matrix is drawn on.

    Symmetric about zero in both colour and scale, so a cell's hue is its
    direction and its saturation is its size, and a scenario that does nothing to a
    metal leaves the surface colour behind. The scale is linear, so a cell's
    colour is proportional to the move it stands for and two cells can be
    compared by eye; past `max_points` it saturates rather than stretching the
    scale for everything else, and the figure prints those cells' numbers so
    nothing is hidden by the clip.
    """
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "relief_load",
        [heatmap["relief_color"], heatmap["middle_color"], heatmap["load_color"]],
    )
    norm = mcolors.Normalize(vmin=-heatmap["max_points"], vmax=heatmap["max_points"])
    return cmap, norm


def matrix_figure(frame: pd.DataFrame, heatmap: dict, plotting: dict):
    """A page-wide figure for `frame`, as tall as its rows make it.

    The columns divide whatever `margin` leaves of the page; the height is
    bought a row at a time, as in `matrix_strip_figure`.
    """
    margin = heatmap["margin"]
    return plt.subplots(
        figsize=(
            plotting["page_width"],
            margin["height"] + heatmap["cell_height"] * len(frame.index),
        ),
        layout="constrained",
    )


def band_scale(levels: list[float], matrix: dict):
    """A discrete colourmap whose bands are `levels`, shaded within each band.

    `levels` are the boundaries in ascending order — the allocation principles'
    parities — so there is one more band than there are levels, and the last one
    runs to `matrix.cap`. A cell's band says which principles would still cover
    the metal it stands for, and its step within that band how deep inside it the
    metal sits, so hue is the state and shade the degree.

    The top band steps geometrically because its values are unbounded while the
    others are penned between two parities; `cap` is where its colour ends, not
    its values, so a cell past it saturates and carries its number.
    """
    bands = matrix["bands"]
    if len(bands) != len(levels) + 1:
        raise ValueError(
            f"compare.scenario_effects.matrix.bands gives {len(bands)} palettes for "
            f"{len(levels)} parity levels; it needs one more palette than levels"
        )
    if any(low >= high for low, high in zip(levels, levels[1:])) or levels[-1] >= matrix["cap"]:
        raise ValueError(
            f"parity levels {levels} must ascend and end below "
            f"compare.scenario_effects.matrix.cap ({matrix['cap']})"
        )

    colors, boundaries = [], [0.0]
    edges = [0.0, *levels, matrix["cap"]]
    for index, (low, high) in enumerate(zip(edges, edges[1:])):
        steps = len(bands[index])
        # geomspace needs a positive start, which only the top band is sure of.
        within = (
            np.geomspace(low, high, steps + 1)
            if index == len(edges) - 2
            else np.linspace(low, high, steps + 1)
        )
        colors.extend(bands[index])
        boundaries.extend(within[1:])
    return (
        mcolors.ListedColormap(colors),
        mcolors.BoundaryNorm(boundaries, len(colors)),
    )


def spectrum_scale(matrix: dict):
    """One ramp from nothing to `matrix.cap`, for a matrix with no thresholds.

    `band_scale` spends hue on which allocation principles would still cover a
    metal, which is a reading only the whole demand charged to the region
    supports. A matrix drawn over one sector alone crosses no parity, so its
    cells carry a level and nothing else and are graded on a single ramp: darker
    is more.

    The ramp is cut into as many steps as `band_scale` draws, so the two matrices
    are quantised alike, and the steps are even, so no boundary in it claims to
    mean anything. `cap` is the one the banded scale ends at, so the two stay
    comparable cell for cell.
    """
    steps = sum(len(band) for band in matrix["bands"])
    ramp = mcolors.LinearSegmentedColormap.from_list("spectrum", matrix["spectrum"])
    return (
        mcolors.ListedColormap(ramp(np.linspace(0.0, 1.0, steps))),
        mcolors.BoundaryNorm(np.linspace(0.0, matrix["cap"], steps + 1), steps),
    )


def band_colorbar(
    fig, mesh, axes, levels: dict[str, float], plotting: dict, *, label,
    orientation: str = "vertical",
):
    """The band scale as a key: one tick per parity, named for its principle.

    The bands are not a continuum, so the bar is read as four labelled regions
    rather than as a gradient — which is why the ticks are the boundaries and not
    a round-number sequence.

    `orientation` is a page-layout decision, not a stylistic one: a vertical bar
    and its tick names cost an inch and a half of *width*, which a matrix printed
    to the width of a portrait page cannot spare, so it goes under the panel and
    costs height instead.
    """
    ink = plotting["ink"]
    bar = fig.colorbar(
        mesh, ax=axes, ticks=list(levels.values()), pad=0.015, fraction=0.035,
        extend="max", extendfrac=0.02, orientation=orientation,
    )
    if orientation == "horizontal":
        # Two lines, so the name stays over its own tick: laid out along the
        # bar, a level and its principle side by side are wide enough to reach
        # the next tick and leave which one they belong to ambiguous.
        bar.ax.set_xticklabels(
            [f"{level:.2f}x\n{name}" for name, level in levels.items()],
            color=ink["secondary"],
        )
    elif orientation == "vertical":
        bar.ax.set_yticklabels(
            [f"{level:.2f}x  {name}" for name, level in levels.items()],
            color=ink["secondary"],
        )
    else:
        raise ValueError(f"unknown colorbar orientation {orientation!r}")
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=ink["secondary"], length=2)
    bar.set_label(label, color=ink["secondary"])
    return bar


def row_tops(count: int, row_blocks: list[int] | None, matrix: dict) -> np.ndarray:
    """The top edge of every row once the blocks are set apart, in cells.

    `row_blocks` are the row indices a block starts at; every block after the
    first is pushed down by `matrix.row_gap` of blank space, so rows that fall
    into categories read as those categories without a rule between them. Rows
    inside a block stay one cell apart, which is what lets a block be drawn as a
    single mesh — neighbouring cells of one mesh share the edge between them, so
    a gap cannot be opened there.
    """
    tops = np.arange(count, dtype=float)
    for start in sorted(set(row_blocks or ()) - {0}):
        if not 0 < start < count:
            raise ValueError(f"row block starts at {start}, outside the {count} rows")
        tops[start:] += matrix["row_gap"]
    return tops


def row_spans(count: int, row_blocks: list[int] | None) -> list[tuple[int, int]]:
    """`row_blocks` as (start, end) pairs covering every row exactly once."""
    starts = sorted(set(row_blocks or ()) | {0})
    return list(zip(starts, [*starts[1:], count]))


def matrix_strip_figure(
    frame: pd.DataFrame, matrix: dict, row_blocks: list[int] | None = None
):
    """A matrix panel with a strip over the columns, sharing their x axis.

    `row_blocks` is what `heat_matrix` will set apart, so the panel grows by the
    blank space between the blocks as well as by the rows themselves.

    The cells are the figure, so it is sized from them outwards: `matrix.margin`
    is the chrome — the row names and the strip's y label beside them, the
    column names and the colour bar below — and the figure that plus the strip
    plus the cells. It is config because the figure has a printed size to hit
    and only the cells can give way to hit it.

    The strip enters the height twice, as its own inch of figure and as its
    share of the gridspec, which is what keeps a cell the height it is asked
    for: given to the ratios alone, a taller strip would take the difference out
    of the cells instead of out of the page.
    """
    margin, strip = matrix["margin"], matrix["strip"]["height"]
    tops = row_tops(len(frame.index), row_blocks, matrix)
    rows = matrix["cell_height"] * (tops[-1] + 1)
    return plt.subplots(
        2, 1,
        figsize=(
            margin["width"] + matrix["cell_width"] * len(frame.columns),
            margin["height"] + strip + rows,
        ),
        gridspec_kw={"height_ratios": [strip, rows]},
        sharex=True,
        layout="constrained",
    )


def level_strip(
    ax,
    frame: pd.DataFrame,
    parity_lines: dict[float, dict],
    matrix: dict,
    plotting: dict,
    *,
    ylabel: str,
) -> None:
    """What the matrix's columns are, over the matrix that acts on them.

    One column of `frame` per thing to draw, indexed in the matrix's column
    order and in the matrix's own units: `low` to `high` is the span every
    scenario leaves the metal in, `reference` the scenario the cells are measured
    against, and `floor` the demand no scenario reaches — the wall `low` can never
    pass, which is what separates a metal the scenarios merely fail to fix from one
    they could never have fixed. Those first three are the strip; `floor` is the
    one thing that is a column rather than a requirement, since a matrix drawn
    with other-sector demand left out has no floor to draw.

    `parity_lines` maps a level to its line's `color` and `linestyle`, so the strip
    and the matrix's bands are the same thresholds in the same colours. `ylabel`
    names the ratio `frame` is in.
    """
    strip, ink = matrix["strip"], plotting["ink"]
    x = np.arange(len(frame)) + 0.5
    span = (frame["high"] - frame["low"]).clip(lower=0.015)
    ax.bar(
        x, span, bottom=frame["low"], width=strip["bar_width"],
        color=strip["range_color"], edgecolor="none", zorder=2,
    )
    ax.plot(
        x, frame["reference"], marker="o", markersize=strip["reference_size"],
        linestyle="none", color=ink["primary"], zorder=5,
    )
    if "floor" in frame:
        ax.plot(
            x, frame["floor"], marker="_", markersize=strip["floor_size"],
            markeredgewidth=1.4, linestyle="none", color=ink["secondary"], zorder=4,
        )
    for level, line in parity_lines.items():
        ax.axhline(level, linewidth=1.0, zorder=3, **line)

    ax.set_ylim(strip["bottom"], matrix["cap"])
    ax.set_ylabel(ylabel, color=ink["secondary"])
    ax.tick_params(length=0, colors=ink["secondary"], labelbottom=False)
    ax.spines[:].set_visible(False)
    ax.grid(axis="y", color=ink["grid"], linewidth=0.6)
    ax.set_axisbelow(True)


def strip_key(
    ax,
    matrix: dict,
    plotting: dict,
    *,
    reference: str,
    parities: dict[str, dict],
    floor: str | None = None,
):
    """`level_strip`'s marks, named inside the strip's own top right corner.

    A key beside the colour bar under the matrix would leave the reader to work
    out which panel each entry belongs to, so the strip carries its own. It is
    drawn on the surface colour: a dashed parity line running through a name
    costs more than a covered bar.
    """
    strip, ink = matrix["strip"], plotting["ink"]
    handles = [
        mpatches.Patch(color=strip["range_color"], label="Range over the scenario set"),
        mlines.Line2D(
            [], [], color=ink["primary"], marker="o", linestyle="none",
            markersize=strip["reference_size"], label=reference,
        ),
    ]
    if floor is not None:
        handles.append(
            mlines.Line2D(
                [], [], color=ink["secondary"], marker="_", linestyle="none",
                markersize=strip["floor_size"], markeredgewidth=1.4, label=floor,
            )
        )
    handles += [
        mlines.Line2D([], [], label=name, **line) for name, line in parities.items()
    ]
    return ax.legend(
        handles=handles, loc="upper right", ncol=strip["key_columns"],
        facecolor=ink["surface"], edgecolor="none", framealpha=1.0,
        borderpad=0.3, labelspacing=0.25, handlelength=1.5, borderaxespad=0.2,
    )


def corner_key(fig, level_with, labels: dict[str, dict]):
    """A handleless key, each entry set the way the names it describes are.

    It goes at the figure's left edge, level with the `level_with` axes (the
    colour bar), which keeps it clear of the row and column names.
    """
    legend = fig.legend(
        handles=[
            mlines.Line2D([], [], linestyle="none", marker="", label=name)
            for name in labels
        ],
        loc="center left", bbox_to_anchor=(0.0, 0.5),
        bbox_transform=mtransforms.blended_transform_factory(
            fig.transFigure, level_with.transAxes
        ),
        frameon=False, borderaxespad=0.0,
        handlelength=0.0, handletextpad=0.0, labelspacing=0.4,
    )
    # Anchored to the colour bar, so it must not move the layout that places it.
    legend.set_in_layout(False)
    for text in legend.get_texts():
        text.set(**labels[text.get_text()])
    return legend


def heat_matrix(
    ax,
    frame: pd.DataFrame,
    cmap,
    norm,
    heatmap: dict,
    plotting: dict,
    *,
    title: str | None,
    subtitle: str | None = None,
    groups: dict[int, str] | None = None,
    row_rules: list[int] | None = None,
    row_blocks: list[int] | None = None,
    numbers: pd.DataFrame | None = None,
    column_label_styles: dict[str, dict] | None = None,
    ylabel: str | None = None,
):
    """`frame` drawn one cell per value, rows top-down in index order.

    Cells whose number passes `annotate_above` carry it, so the sizes that matter
    are readable without printing a number on every cell of the matrix and
    burying the pattern the colour is there for. `numbers` is that number where
    it is not the value the colour is on — a matrix coloured by where a scenario
    leaves a metal still wants to print how far it moved it. The number is set in
    the surface colour once its own cell is dark enough for ink not to read on it.

    `groups` blocks the columns: it maps the index a block starts at to that
    block's name, and each block after the first is ruled off from the one
    before. The names go over the axes, which is why this and not the caller
    sets the title's padding. A block is only as wide as the columns it holds
    and its name is not, so the names alternate between two lines: a long name
    over a one-column block then runs over its neighbour's column rather than
    over its neighbour's name. The rows have the two plainer things instead of a
    name: `row_blocks`, the indices a block of rows starts at, set apart by the
    blank space `row_tops` opens above each one; and `row_rules`, the indices to
    draw a rule above, for a row that is a different kind of thing from the ones
    under it rather than merely the head of the next block. A rule over a block
    boundary is drawn down the middle of that blank space.

    `column_label_styles` sets individual column names apart from the rest — a
    dict per column of keyword arguments for its Text, so the matrix can carry a
    second, quieter encoding in the way a name is written rather than in another
    mark, as `category_axis` does for a bar.

    `ylabel` names what a row is, beside the row names themselves. It is worth
    the width only where the rows are one kind of thing the reader has to hold
    on to, so it is optional and no matrix draws one by default.

    Returns the mesh and those block names, because they sit outside the axes:
    `save_figure` replaces matplotlib's own artist collection with the one it is
    given, so a caller that does not pass them on has them cropped away.
    """
    ink = plotting["ink"]
    header = heatmap["header_pad"] if groups else 0.0
    panel_title(ax, plotting, title, subtitle, extra_pad=header)
    values = frame.to_numpy(dtype=float)
    tops = row_tops(len(frame.index), row_blocks, heatmap)
    columns = np.arange(len(frame.columns) + 1)
    # One mesh per block of rows, since the blank space between blocks cannot be
    # drawn inside a mesh. They share the colourmap and the norm, so any of them
    # keys the colourbar.
    for start, end in row_spans(len(frame.index), row_blocks):
        mesh = ax.pcolormesh(
            columns, tops[start] + np.arange(end - start + 1), values[start:end],
            cmap=cmap, norm=norm, edgecolors=ink["surface"], linewidth=0.7,
        )
    # `column_label_rotation` is the heatmap spec's, because it is a consequence
    # of what a column is: slanted where its name is several words, upright where
    # it is one and the slant would only drift it off its own column.
    rotation = heatmap["column_label_rotation"]
    ax.set_xticks(
        np.arange(len(frame.columns)) + 0.5, frame.columns,
        rotation=rotation,
        ha="right" if rotation % 90 else "center",
        color=ink["secondary"],
    )
    if column_label_styles is not None:
        for column, text in zip(frame.columns, ax.get_xticklabels()):
            text.set(**column_label_styles[column])
    ax.set_yticks(tops + 0.5, frame.index, color=ink["secondary"])
    if ylabel is not None:
        ax.set_ylabel(ylabel, color=ink["secondary"])
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)

    printed = values if numbers is None else numbers.to_numpy(dtype=float)
    for row, column in zip(*np.nonzero(np.abs(printed) >= heatmap["annotate_above"])):
        # Ink on a pale cell, surface on a dark one, off the colour the cell
        # actually came out — which a norm's own scale cannot be read for once
        # the scale is banded rather than continuous.
        red, green, blue, _ = cmap(norm(values[row, column]))
        dark = (0.299 * red + 0.587 * green + 0.114 * blue) < 0.55
        ax.annotate(
            f"{printed[row, column]:+.0f}",
            xy=(column + 0.5, tops[row] + 0.5),
            ha="center", va="center", fontsize=heatmap["annotate_size"],
            color=ink["surface"] if dark else ink["primary"],
        )

    # Each block after the first is ruled off; the first needs no rule, since
    # the panel edge already divides it.
    headers = []
    for order, (start, name) in enumerate(sorted((groups or {}).items())):
        if order:
            ax.axvline(start, color=ink["primary"], linewidth=1.2, zorder=6)
        headers.append(
            ax.annotate(
                name,
                xy=(start + 0.15, 0.0),
                xytext=(0.0, header - 4.0 + (order % 2) * heatmap["header_line"]),
                textcoords="offset points",
                ha="left", va="bottom",
                fontsize=8.0, color=ink["secondary"],
                annotation_clip=False,
            )
        )

    for row in row_rules or ():
        # Down the middle of the blank space where the row heads a block, so the
        # rule divides the two blocks rather than sitting against the cells below.
        blank = tops[row] - (tops[row - 1] + 1.0 if row else 0.0)
        ax.axhline(
            tops[row] - blank / 2, color=ink["primary"], linewidth=1.2, zorder=6
        )
    return mesh, headers


def _covered(box: tuple, placed: list[tuple]) -> float:
    """How much of an (x0, y0, x1, y1) display box the already placed ones cover.

    A fraction of `box`'s own area, so it means the same thing whatever the name
    is: 0 is clear and 1 is buried. Overlaps are summed rather than unioned —
    two names over the same one is worse than either alone, which is what the
    sum says and a union would not.
    """
    x0, y0, x1, y1 = box
    area = (x1 - x0) * (y1 - y0)
    return sum(
        max(0.0, min(x1, ox1) - max(x0, ox0)) * max(0.0, min(y1, oy1) - max(y0, oy0))
        for ox0, oy0, ox1, oy1 in placed
    ) / area


def _crossed(box: tuple, segments: list[tuple]) -> float:
    """How far the segments cut across an (x0, y0, x1, y1) display box.

    Liang–Barsky clips each segment to the box; the chord is returned as a
    fraction of the box's own diagonal, so a line clipping a corner costs a
    fraction of what one bisecting the name does.
    """
    x0, y0, x1, y1 = box
    diagonal = np.hypot(x1 - x0, y1 - y0)
    crossed = 0.0
    for (sx0, sy0), (sx1, sy1) in segments:
        dx, dy = sx1 - sx0, sy1 - sy0
        enter, leave = 0.0, 1.0
        for edge, distance in (
            (-dx, sx0 - x0), (dx, x1 - sx0), (-dy, sy0 - y0), (dy, y1 - sy0)
        ):
            if edge == 0.0:
                if distance < 0.0:  # parallel to this edge and outside it
                    enter, leave = 1.0, 0.0
                    break
                continue
            end = distance / edge
            if edge < 0.0:
                enter = max(enter, end)
            else:
                leave = min(leave, end)
        if leave > enter:
            crossed += (leave - enter) * np.hypot(dx, dy) / diagonal
    return crossed


# How much of a label's own box lies before its anchor, per alignment: a name is
# drawn from its anchor, so this is what turns an offset into a box.
_ANCHOR = {"left": 0.0, "bottom": 0.0, "center": 0.5, "right": 1.0, "top": 1.0}

# The sides `label_points` may pin a name to: level with its point, or square
# over or under it, as (x, y) offset -> whether that placement is on the side.
_PINNED_SIDES = {
    "left": lambda ox, oy: ox < 0 and oy == 0,
    "right": lambda ox, oy: ox > 0 and oy == 0,
    "above": lambda ox, oy: ox == 0 and oy > 0,
    "below": lambda ox, oy: ox == 0 and oy < 0,
}


def _clear_of(box: tuple, points: np.ndarray) -> float:
    """Display distance from an (x0, y0, x1, y1) box to the nearest of `points`."""
    x0, y0, x1, y1 = box
    gaps_x = np.maximum(np.maximum(x0 - points[:, 0], 0.0), points[:, 0] - x1)
    gaps_y = np.maximum(np.maximum(y0 - points[:, 1], 0.0), points[:, 1] - y1)
    return float(np.hypot(gaps_x, gaps_y).min())


def label_points(
    ax,
    frame: pd.DataFrame,
    names: dict[str, str],
    colors: dict[str, str],
    label: dict,
    label_styles: dict[str, dict] | None = None,
    traced: bool = False,
    rules: list[float] | None = None,
    pinned: dict[str, str] | None = None,
) -> None:
    """Name every row of `frame` beside its starting point, without overprinting.

    A name is tried at `label.offset` from its point, at that offset mirrored into
    the other three quadrants, and at both stepped out by the multiples in
    `label.reach` — a grid of placements from the closest ring outwards. The
    crowded corner of a scatter has no free ring, so a placement is **scored**
    rather than accepted or rejected, and the cheapest wins:

    - `cost.overprint` per unit of the name a marker or another name covers,
    - `cost.crossing` per unit of it a trace or a rule cuts through,
    - `cost.spill` per unit of it hanging outside the panel,
    - `cost.ambiguity` per offset-length another metal's marker is nearer to the
      name than the metal's own is,
    - `cost.drift` per offset-length the name sits out from its point,
    - `cost.leftward` once for a name set left of its point, since a name reads
      on from the mark it follows.

    Ambiguity and drift are what keep a name readable as a name *of* something: drift
    holds it against its own point until the room there is gone, and ambiguity
    stops it settling next to somebody else's marker on the way out. The first
    three are what it is escaping. A hairline under a name can be read through
    and a name over it cannot, which is why crossing costs a fraction of what
    overprinting does.

    `traced` declares that the frame carries the `x_to`/`y_to` of the arrows
    `traced_points` draws, so their far ends and the arrows themselves are
    obstacles too — without it a name dodges the marker it belongs to and lands
    on the line leaving it. `rules` are the data y of any lines drawn across the
    whole panel, `reference_lines`' levels being the ones these panels carry: a
    name over one is struck through by it.

    Each box is the width the string actually sets to in the font and weight it
    is drawn in (`_TEXT_METRICS`, which needs no renderer), so a name set bold
    takes the room it really takes rather than an average glyph's; its height is
    that of "lp", which is what matplotlib lays a single line out on. A placed
    name keeps `label.gap` clear around it, so two names never run together. The
    geometry is measured rather than drawn, so a placement is the same on every run.

    `pinned` holds a key's name to one side of its point (`_PINNED_SIDES`) where
    the scoring's pick reads worse; the placements on that side are still scored.

    `label_styles` sets individual names apart from the rest — a dict per key of
    keyword arguments for its Text — so a panel already spending colour on one
    thing can carry a second encoding in how a name is written, as
    `category_axis` does for a bar. It is applied after the colour, so a style
    naming `color` overrides the point's own, and it is what the width is
    measured against.
    """
    pinned = {} if pinned is None else pinned
    unknown = {key: side for key, side in pinned.items() if side not in _PINNED_SIDES}
    if unknown or not set(pinned) <= set(frame.index):
        raise ValueError(
            f"pinned names {pinned}: sides must be one of {sorted(_PINNED_SIDES)} "
            f"and keys rows of the frame"
        )
    dx, dy = label["offset"]
    size = label["size"]
    cost = label["cost"]
    scale = ax.figure.dpi / 72.0  # points -> display pixels
    _, line, _ = _TEXT_METRICS.get_text_width_height_descent(
        "lp", FontProperties(size=size), ismath=False
    )
    line *= scale
    marker_half = 0.5 * scale * label["clearance"]
    step = np.hypot(dx, dy) * scale  # the offset's own length, the unit of drift

    def text_width(key):
        """`names[key]` as it will be set, in display pixels.

        A style that names neither weight nor slant leaves the FontProperties on
        the rcParams the Text itself would fall back to, so the measurement and
        the drawing agree without a default being written down twice.
        """
        text_style = {} if label_styles is None else label_styles[key]
        prop = FontProperties(size=size)
        if "weight" in text_style:
            prop.set_weight(text_style["weight"])
        if "style" in text_style:
            prop.set_style(text_style["style"])
        points, _, _ = _TEXT_METRICS.get_text_width_height_descent(
            names[key], prop, ismath=False
        )
        return points * scale

    def marker_boxes(centres):
        return [
            (px - marker_half, py - marker_half, px + marker_half, py + marker_half)
            for px, py in centres
        ]

    starts = ax.transData.transform(frame[["x", "y"]].to_numpy())
    # Every marker drawn, and which row it belongs to: a name is ambiguous where
    # it settles nearer somebody else's than its own.
    centres, owners = starts, np.arange(len(frame))
    placed = marker_boxes(starts)
    segments = []
    if traced:
        ends = ax.transData.transform(frame[["x_to", "y_to"]].to_numpy())
        centres = np.vstack([starts, ends])
        owners = np.concatenate([owners, owners])
        placed += marker_boxes(ends)
        segments += [(tuple(start), tuple(end)) for start, end in zip(starts, ends)]
    for level in rules or ():
        # A rule spans the panel, so it is a segment from edge to edge at its own
        # height. Drawn in data, read in display, like everything else here.
        left, right = ax.get_xlim()
        (lx, ly), (rx, ry) = ax.transData.transform([(left, level), (right, level)])
        segments.append(((lx, ly), (rx, ry)))

    # (dx, dy, ha, va) for every rung of the ladder, closest first: a name steps
    # out only as far as it has to, and in whichever direction has room. A step
    # out also earns the two placements that sit square to the point — level with
    # it, or over and under it — which are the clearest way to hang a name off
    # something once it is no longer against it. They are not offered at the
    # first rung, where the point's own marker is in the way.
    steps = label["reach"]
    sides = ((1.0, "left"), (-1.0, "right"))
    rises = ((1.0, "bottom"), (-1.0, "top"))
    candidates = sorted(
        [
            (side * across * dx, rise * up * dy, ha, va)
            for across in steps
            for up in steps
            for side, ha in sides
            for rise, va in rises
        ]
        + [
            (side * across * dx, 0.0, ha, "center")
            for across in steps[1:]
            for side, ha in sides
        ]
        + [
            (0.0, rise * up * dy, "center", va)
            for up in steps[1:]
            for rise, va in rises
        ],
        key=lambda placement: np.hypot(placement[0], placement[1]),
    )
    # Both transforms read the axes' current position, so a box tested in axes
    # fraction stays where it is when constrained layout moves the panel at draw.
    to_fraction = ax.transAxes.inverted()

    for row_number, ((key, row), (px, py)) in enumerate(zip(frame.iterrows(), starts)):
        width, height = text_width(key), line
        strangers = centres[owners != row_number]
        own = centres[owners == row_number]
        best = None
        for ox, oy, ha, va in candidates:
            if key in pinned and not _PINNED_SIDES[pinned[key]](ox, oy):
                continue
            x0 = px + ox * scale - width * _ANCHOR[ha]
            y0 = py + oy * scale - height * _ANCHOR[va]
            box = (x0, y0, x0 + width, y0 + height)
            (fx0, fy0), (fx1, fy1) = to_fraction.transform(
                [(box[0], box[1]), (box[2], box[3])]
            )
            # What of the name hangs over each edge of the panel, as a fraction
            # of the name: it may lean out, at a price.
            spill = sum(
                max(0.0, over) / span
                for over, span in (
                    (-fx0, fx1 - fx0), (fx1 - 1.0, fx1 - fx0),
                    (-fy0, fy1 - fy0), (fy1 - 1.0, fy1 - fy0),
                )
            )
            penalty = (
                cost["overprint"] * _covered(box, placed)
                + cost["crossing"] * _crossed(box, segments)
                + cost["spill"] * spill
                + cost["ambiguity"]
                * max(0.0, _clear_of(box, own) - _clear_of(box, strangers))
                / step
                + cost["drift"] * (np.hypot(ox, oy) * scale / step - 1.0)
                + cost["leftward"] * (ox < 0)
            )
            if best is None or penalty < best[0]:
                best = (penalty, ox, oy, ha, va, box)
        _, ox, oy, ha, va, box = best
        gap = label["gap"] * scale
        placed.append((box[0] - gap, box[1] - gap, box[2] + gap, box[3] + gap))
        text = ax.annotate(
            names[key],
            xy=(row["x"], row["y"]),
            xytext=(ox, oy),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=size,
            color=colors[key],
            zorder=5,
        )
        if label_styles is not None:
            text.set(**label_styles[key])


def quadrant_split(ax, x: float, y: float, quadrants: dict, notes: dict) -> None:
    """A crosshair at (`x`, `y`) dividing the panel into four, each corner named.

    `notes` maps the corner — "upper left", "upper right", "lower left", "lower
    right" — to what sitting in it means. A corner left out is not annotated.
    """
    for level, axline in ((x, ax.axvline), (y, ax.axhline)):
        axline(level, color=quadrants["color"], linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
    if not quadrants["annotate"]:
        return
    corners = {
        "upper left": (0.015, 0.985, "left", "top"),
        "upper right": (0.985, 0.985, "right", "top"),
        "lower left": (0.015, 0.015, "left", "bottom"),
        "lower right": (0.985, 0.015, "right", "bottom"),
    }
    for corner, note in notes.items():
        fx, fy, ha, va = corners[corner]
        ax.annotate(
            note,
            xy=(fx, fy),
            xycoords="axes fraction",
            ha=ha,
            va=va,
            fontsize=7.5,
            style="italic",
            color=quadrants["color"],
            zorder=1,
        )


def marker_handles(
    keys,
    markers: dict[str, str],
    names: dict[str, str],
    color: str,
    colors: dict[str, str] | None = None,
) -> list:
    """Legend handles for point shapes, in one neutral colour by default: the
    shape is what the entry is about, and the colour says something else.

    `colors` overrides that per key, for a legend where the shape and the colour
    are two encodings of the same thing.
    """
    return [
        mlines.Line2D(
            [], [],
            color=colors[key] if colors is not None else color,
            marker=markers[key],
            linestyle="none",
            markersize=6,
            label=names[key],
        )
        for key in keys
    ]


def patch_handles(keys, colors: dict[str, str], names: dict[str, str]) -> list:
    """Legend handles for filled segments, in the order given."""
    return [
        mpatches.Patch(facecolor=colors[key], label=names[key], linewidth=0)
        for key in keys
    ]


def styled_patch_handles(keys, styles: dict[str, dict], names: dict[str, str]) -> list:
    """Legend handles for a fill that carries more than its colour.

    `styles` holds the same per-key Patch keywords `stacked_bars`'s `row_styles`
    takes, so the key is drawn with the hatch and edge the bars were drawn with
    rather than with an approximation of them.
    """
    return [mpatches.Patch(label=names[key], **styles[key]) for key in keys]


class _SwatchRun(HandlerBase):
    """Draws its entry as one swatch per style, side by side across the handle."""

    def __init__(self, styles: list[dict]):
        super().__init__()
        self.styles = styles

    def create_artists(
        self, legend, orig_handle, xdescent, ydescent, width, height, fontsize, trans
    ):
        step = width / len(self.styles)
        return [
            mpatches.Rectangle(
                (index * step - xdescent, -ydescent), step, height,
                transform=trans, **style,
            )
            for index, style in enumerate(self.styles)
        ]


def swatch_run(keys, styles: dict[str, dict], label: str) -> tuple:
    """One legend entry for a fill drawn in several shades: a swatch per key, in
    order and side by side, under one `label`, where `styled_patch_handles` would
    spend a row on each.

    Returns the handle and the `handler_map` the legend needs to draw it so.
    """
    handle = mpatches.Patch(label=label)
    return handle, {handle: _SwatchRun([styles[key] for key in keys])}


def lead_column(first: list, rest: list, ncol: int) -> list:
    """Legend handles putting `first` in a column of its own and flowing `rest`
    through the other `ncol - 1`."""
    rows = -(-len(rest) // (ncol - 1))
    if len(first) > rows:
        raise ValueError(
            f"{len(first)} entries cannot lead a {ncol}-column legend whose other "
            f"columns hold {rows}; use fewer columns"
        )
    return column_handles([first, *(rest[i : i + rows] for i in range(0, len(rest), rows))])


def column_handles(columns: list[list]) -> list:
    """Legend handles putting each of `columns` in a legend column of its own, for
    a legend drawn with `ncol=len(columns)`.

    A legend fills column by column, the first columns taking the odd entries,
    so every column is padded with blank entries to the length of the longest.
    """
    rows = max(len(column) for column in columns)
    return [
        handle
        for column in columns
        for handle in (*column, *blank_handles(rows - len(column)))
    ]


def blank_handles(count: int) -> list:
    """Legend entries that draw nothing, each holding one row of its column."""
    return [
        mlines.Line2D([], [], linestyle="none", marker="", label="")
        for _ in range(count)
    ]


def line_handles(
    keys, styles: dict[str, dict], names: dict[str, str], color_key: str, style_key: str
) -> list:
    """Legend handles for reference lines, in the order given."""
    return [
        mlines.Line2D(
            [], [],
            color=styles[key][color_key],
            linestyle=styles[key][style_key],
            linewidth=1.1,
            label=names[key],
        )
        for key in keys
    ]


def save_figure(
    fig, directory: Path, name: str, plotting: dict, extra_artists: tuple = ()
) -> None:
    """Write `name` in every configured format.

    `extra_artists` must name every figure-level artist (legends, row headers,
    suptitles): passing bbox_extra_artists replaces matplotlib's own collection,
    so anything left out is cropped away.
    """
    savefig = plotting["savefig"]
    for suffix in savefig["formats"]:
        fig.savefig(
            Path(directory) / f"{name}.{suffix}",
            dpi=savefig["dpi"],
            bbox_inches="tight",
            bbox_extra_artists=extra_artists,
        )
