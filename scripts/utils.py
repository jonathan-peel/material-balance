import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pandas as pd

# utils is imported both as `scripts.utils` (from the .smk files, repo root on
# sys.path) and as `utils` (from scripts run via Snakemake's script: directive,
# which puts scripts/ on sys.path instead).
try:
    from scripts.info_schemas import MineralGroup, MineralInfo
except ModuleNotFoundError:
    from info_schemas import MineralGroup, MineralInfo


def override_config(*inputs):
    """
    Combine multiple config sources into a single config dictionary. Later inputs will
    add to or overwrite earlier ones using deep merge for nested dictionaries.

    Args:
        *inputs: Variable number of inputs, each can be either:
            - str: Path to a YAML config file
            - dict: Configuration dictionary

    Returns:
        dict: Combined configuration dictionary
    """
    import yaml

    def deep_merge(base_dict, override_dict):
        """Recursively merge two dictionaries."""
        result = base_dict.copy()
        for key, value in override_dict.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    result = {}

    for input_item in inputs:
        if isinstance(input_item, str):
            # Load YAML file
            with open(input_item) as file:
                config_dict = yaml.safe_load(file)
        elif isinstance(input_item, dict):
            # Use dictionary directly
            config_dict = input_item
        else:
            raise TypeError(
                f"Input must be str (file path) or dict, got {type(input_item)}"
            )

        if config_dict is not None:
            result = deep_merge(result, config_dict)

    return result


@contextmanager
def inject_modules(*, root: str | Path, evict: list[str] | None = None):
    """Temporarily adjust Python import resolution for packaged code.

    Args:
        root: A single directory to prepend to `sys.path` for the context
            (use this to make packages importable, e.g. "pypsa-eur").
        evict: Temporarily remove given top-level packages from sys.modules so
            that imports can resolve against provided `root` or explicitly injected
            modules (useful when a same-named package exists elsewhere, e.g. local
            `scripts` vs pypsa-eur's `scripts`).

    Notes:
        - Existing modules already present in `sys.modules` are left intact unless
          listed in `evict`.
        - Only modules injected by this context are removed on exit. Evicted ones
          are restored to their original objects, and any newly imported submodules
          under evicted packages are cleaned up.
        - Any root paths inserted into `sys.path` are removed on exit.
    """
    inserted_paths: list[str] = []
    injected_modules: list[str] = []
    evicted_saved: dict[str, ModuleType] = {}
    pre_existing_modules = set(sys.modules.keys())

    def _as_path(p: str | Path) -> Path:
        return Path(p)

    try:
        # 0) Evict conflicting packages if requested
        if evict:
            for name in evict:
                if name in sys.modules:
                    module_obj = sys.modules[name]
                    if not isinstance(module_obj, ModuleType):
                        # In odd cases, a non-module might be present; skip eviction
                        continue
                    evicted_saved[name] = module_obj
                    del sys.modules[name]

        # 1) Prepend any root search paths
        r_str = str(_as_path(root).resolve())
        if r_str not in sys.path:
            sys.path.insert(0, r_str)
            inserted_paths.append(r_str)

        yield
    finally:
        # Restore evicted modules and clean up any submodules imported during the context
        if evicted_saved:
            # Remove any submodules imported during context under evicted packages
            current_keys = list(sys.modules.keys())
            for key in current_keys:
                top = key.split(".")[0]
                if top in evicted_saved and key not in pre_existing_modules:
                    # This submodule didn't exist before; remove it
                    sys.modules.pop(key, None)

            # Restore the original top-level modules
            for name, module_obj in evicted_saved.items():
                sys.modules[name] = module_obj

        # Remove injected modules only
        for name in injected_modules:
            if name in sys.modules:
                del sys.modules[name]

        # Remove any paths we inserted (by value)
        if inserted_paths:
            sys.path[:] = [p for p in sys.path if p not in inserted_paths]


def system_scenario_label(network_scenario: str, mga_scenario: str | None) -> str:
    """Label for a system scenario = a (pypsa run, mga variant) pair.

    This is the shared key that names the `scenario` dimension of the pypsa
    summary and that calculate_metal_demand looks capacities up by. Defined once
    here so the Snakefile (which builds the file paths) and the demand script
    (which resolves each metal scenario to a capacity) agree on the spelling.

    A plain cost-optimal run (falsy mga_scenario, i.e. null in the config) keeps
    its bare run name so those scenarios read the same as before MGA existed; an
    MGA re-solve is a sibling label `<run>-<mga>` (e.g. base-min_wind).
    """
    if not mga_scenario:
        return network_scenario
    return f"{network_scenario}-{mga_scenario}"


def get_study_minerals() -> list[str]:
    info = pd.read_csv("data/mineral_info.csv")
    return info.loc[
        info[MineralInfo.group] != MineralGroup.helper, MineralInfo.mineral
    ].tolist()


def get_mineral_groups(config: dict, mineral_info_path) -> dict[str, dict]:
    """The `mineral_groups` config block, checked against the metals claiming it.

    One entry carries everything a figure needs for a group: the `nice_name` it
    writes and the `color` it bands with. `data/mineral_info.csv` holds the key.
    `helper` is the one MineralGroup with no entry -- its rows are supply-side
    hosts, never a tracked metal.

    Read at DAG-build time by the rules and at run time by the notebooks, as
    `grid_parameters` and `route_verdicts` are; hence the explicit path, since the
    rules run from the repo root and an interactive notebook from notebooks/.
    """
    declared = dict(config["mineral_groups"])
    claimed = set(pd.read_csv(mineral_info_path)[MineralInfo.group])
    known = {str(group) for group in MineralGroup}
    for source, groups in (("config mineral_groups", declared), ("mineral_info.csv", claimed)):
        unknown = sorted(set(groups) - known)
        if unknown:
            raise ValueError(
                f"{source} uses {unknown}, which info_schemas.MineralGroup does not declare"
            )
    drawn = claimed - {str(MineralGroup.helper)}
    if drawn != set(declared):
        raise ValueError(
            "config mineral_groups and the `group` column of mineral_info.csv disagree: "
            f"no entry for {sorted(drawn - set(declared))}, "
            f"no metal claims {sorted(set(declared) - drawn)}"
        )
    return declared
