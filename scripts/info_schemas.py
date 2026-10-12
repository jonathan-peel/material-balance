"""Column names and category values for the data tables and the config structures
that index them.

Kept in one place so the strings are defined once instead of scattered across the
scripts and rules; StrEnum members are real strings, so they index pandas directly
(``df[LciInfo.activity]``, ``groupby(LciInfo.database)``) and compare equal to the
plain strings that come out of the YAML config.
"""

from enum import StrEnum


class ScalarTable(StrEnum):
    """Columns shared by every transcribed-scalar table in data/ -- one named
    quantity per row, currently data/grid_parameters.csv and
    data/conductor_areas.csv.

    `unit` and `source` are documentation -- what the number means and the page it
    was read off, spelled out in data/source/sources.md -- and only `value` reaches
    the arithmetic. The rows of each such table are their own enum (GridParameter,
    ConductorParameter), since those differ; the columns do not, so they are
    declared once. A table may carry further columns of its own (see
    GridParameterColumn).
    """

    parameter = "parameter"
    value = "value"
    unit = "unit"
    source = "source"


class LciInfo(StrEnum):
    """Columns of data/lci_info.csv, which names the activity standing for each
    LCI-sourced sub-technology. Which sub-technologies exist, and which of them are
    LCI-sourced at all, is declared in the config (see IntensitySource)."""

    activity = "activity"
    database = "database"
    unit = "unit"
    multiplier = "multiplier"
    location = "location"
    sub_technology = "sub_technology"


class MetalDensity(StrEnum):
    """Columns of data/metal_densities.csv. Metals are named as the study mineral
    list names them."""

    metal = "Metal"
    density = "Density kg/m3"
    source = "Source"


class ConductorComparison(StrEnum):
    """Columns of build/lci/conductor_substitution_effect.csv, one row per (conductor
    pair, mineral). `delta` is the amount that moves and `ratio` how many times more
    the aluminium dataset embodies -- neither implies the other, so both are kept.
    `ratio` is empty where the copper parent embodies none of the mineral; `scale` is
    a sort key and does not reach the file."""

    copper_sub_technology = "copper_sub_technology"
    aluminium_sub_technology = "aluminium_sub_technology"
    unit = "unit"
    mineral = "mineral"
    copper_intensity = "copper_intensity"
    aluminium_intensity = "aluminium_intensity"
    delta = "delta"
    ratio = "ratio"
    scale = "scale"


class ConductorParameter(StrEnum):
    """The `parameter` rows of data/conductor_areas.csv.

    The two conductor cross sections that one published inventory gives as carrying
    the same current at the same loss. Their ratio, weighted by the metal densities
    in data/metal_densities.csv, is the mass of aluminium that stands in for a
    kilogram of copper. Both are read off a page, so they live in data/ with the
    rest of this repo's transcribed literature rather than in the config.
    """

    aluminium_conductor_area = "aluminium_conductor_area"
    copper_conductor_area = "copper_conductor_area"


class GridConductorInfo(StrEnum):
    """Columns of data/grid_conductor_info.csv, which pairs each aluminium-conductor
    grid sub-technology with the copper one it is derived from, and says how much of
    that dataset's copper is conductor (the rest -- switchgear, earthing -- stays)."""

    sub_technology = "sub_technology"
    copper_sub_technology = "copper_sub_technology"
    conductor_copper_share = "conductor_copper_share"


class Intensity(StrEnum):
    """Metadata columns of the mineral-intensity tables, all of them build outputs
    (build/lci/mineral_intensity_*.csv). Every other column is a mineral."""

    sub_technology = "sub_technology"
    unit = "unit"
    database = "database"


class IntensitySource(StrEnum):
    """Values of sub_technology_info.<sub_technology> in the config: where a
    sub-technology's mineral intensity is taken from. Every sub-technology is measured
    on one boundary, the LCA, so a source reporting a bill of materials rather than an
    inventory becomes a foreground activity of its own (rule build_bom_foreground_db)
    and is named in data/lci_info.csv like the rest.
    """

    # Computed from the activity data/lci_info.csv names for the sub-technology --
    # ecoinvent, premise, or one of the derived foregrounds.
    lci = "lci"
    # Another sub-technology's LCI intensity, scaled per mineral by
    # data/motor_substitution_info.csv.
    derived = "derived"


class MotorSubstitutionInfo(StrEnum):
    """Columns of data/motor_substitution_info.csv, which derives a motor
    sub-technology from the one it shares a stator, housing and shaft with by giving
    the minerals whose content the rotor changes. A mineral with no row is carried
    over untouched."""

    sub_technology = "sub_technology"
    base_sub_technology = "base_sub_technology"
    mineral = "mineral"
    factor = "factor"
    reason = "reason"


class BillOfMaterials(StrEnum):
    """Columns of data/bill_of_materials.csv: one row per (sub-technology, part,
    material), in kg per MW as its source prints it. A transcription and nothing else;
    which dataset stands for a material is a decision and lives in BomMaterialInfo.
    `part` is the assembly the row belongs to as its own source divides the plant.
    """

    sub_technology = "sub_technology"
    database = "database"
    part = "part"
    material = "material"
    kg_per_mw = "kg_per_mw"


class BomMaterialInfo(StrEnum):
    """Columns of data/bom_material_info.csv: which database activity supplies each
    material a bill of materials names.

    `activity_per_kg` is the amount of that activity's reference product, in its own
    `unit`, per kg of the material as the bill reports it -- 1 where the bill reports
    the dataset's own product, an inverse density where the market sells volume
    (concrete), a stoichiometric inverse where the bill reports an element and the
    market sells its oxide (Carrara's magnet REEs). `unit` is checked against the
    activity, so a regraded dataset fails rather than changing the basis silently.

    `mineral` names the study metal the material is bought *as*, blank for an alloy or
    a multi-element compound whose metals arrive through the LCA instead. It reaches no
    arithmetic: reconcile_metal_selection reads it to catch a metal the foreground buys
    and does not count.
    """

    material = "material"
    activity = "activity"
    location = "location"
    unit = "unit"
    activity_per_kg = "activity_per_kg"
    mineral = "mineral"
    basis = "basis"


class MineralInfo(StrEnum):
    """Columns of data/mineral_info.csv."""

    mineral = "mineral"
    # How a crowded figure writes the metal: its chemical symbol, or for graphite,
    # tracked as a battery-grade material rather than as carbon, its name.
    short_name = "short_name"
    group = "group"
    type = "type"
    host_metal = "host_metal"
    # The mineral's label in each upstream source, used to locate its data.
    iea_name = "iea_name"
    schlichenmaier_name = "schlichenmaier_name"
    bieuville_name = "bieuville_name"
    # Which world series anchors the level of a metal no MSA chapter covers
    # (see rules/ned.smk); blank for every metal one does.
    world_anchor_source = "world_anchor_source"
    # The data/msa_consumption.csv row the metal's consumption level is read from
    msa_name = "msa_name"
    ned_basis = "ned_basis"


class FlowRoute(StrEnum):
    """Columns of build/lci/mineral_flows_raw.csv, the raw LCA record: how much of
    each mineral one functional unit disturbs, and by which route.

    The `route` is the reference product of the dataset that emits the flow -- the
    product that ore was mined for. It is the one thing that says whether the metal
    is what the buyer was paying for, and so the key the study's reading of the flow
    is decided on (RouteInfo). One row per (activity, mineral, route); the emitting
    datasets behind a route are summed, since the verdict is a property of the
    product, not of the mine.
    """

    activity = "activity"
    database = "database"
    location = "location"
    mineral = "mineral"
    route = "route"
    amount = "amount"


class RouteInfo(StrEnum):
    """Columns of data/lci_route_info.csv: whether a mineral's `natural resource /
    in ground` flow, arriving by a given route, is metal the functional unit
    actually contains.

    The flow measures the element *disturbed in the ore*, not the element that ends
    up in the product, and the same metal reaches a product both ways. Keying the
    decision on the route separates them, because the route names what the ore was
    mined for: gallium emitted by a `bauxite` dataset rides along in aluminium's ore
    (~70 ppm, so every aluminium-containing product picks up ~3.1e-04 kg/kg whether
    or not any is recovered), while gallium emitted by `gallium, in Bayer liquor from
    aluminium production` was bought as gallium. Likewise neodymium via `iron ore
    concentrate` is Bayan Obo's REE content allocated onto its iron-ore co-product,
    and neodymium via `rare earth oxide concentrate, 50% REO` is a magnet's.
    """

    mineral = "mineral"
    route = "route"
    verdict = "verdict"
    # Why, where a reader would otherwise ask. Blank where the route speaks for itself.
    note = "note"


class LciResourceFlow(StrEnum):
    """Values of data/lci_route_info.csv's `verdict` (see RouteInfo)."""

    # The route is a product the mineral is mined or refined for, so the flow is
    # metal the functional unit contains. Counted as demand.
    embodied = "embodied"
    # The route is some other metal's product and the mineral merely rides in its
    # ore. Dropped; where such a metal has real demand it comes from an `embodied`
    # route, or from the literature rows.
    host_ore_passenger = "host_ore_passenger"
    # The flow is metal the functional unit contains, but of a grade the tracked
    # supply series does not cover, so it competes for none of it. Dropped, and the
    # metal's scope narrows to the grade that is tracked -- graphite is battery
    # grade, and refractory or electrode graphite is another commodity.
    off_grade = "off_grade"


class MsaConsumption(StrEnum):
    """Columns of data/msa_consumption.csv: what one Material System Analysis
    chapter reports for one material, transcribed with one row per *MSA material*.
    """

    material = "msa_material"
    eu_use_consumption = "eu_use_consumption"
    world_production = "world_production"
    unit = "unit"
    reference_year = "reference_year"  # spans 2013..2020
    reference_region = "reference_region"  # EU27 or EU28
    world_production_stage = "world_production_stage"  # mine, smelter, refinery
    msa_report = "msa_report"
    eu_source_page = "eu_source_page"
    world_source_page = "world_source_page"


class MsaRegion(StrEnum):
    eu27 = "EU27"
    eu28 = "EU28"


class MsaEndUse(StrEnum):
    """Columns of data/msa_end_use_info.csv: one slice of an MSA end-use pie,
    plus this study's verdict on it.

    The representative product comes from the table the chapter prints under the pie,
    and is what the verdict is judged on, since the slice labels mislead
    (e.g., indium's "Batteries" are button cells).
    """

    material = "msa_material"
    # `msa_end_use` checks the two tables agree on both, so naming it twice cannot drift
    # into naming it differently.
    msa_report = "msa_report"
    application = "application"
    # From the chapter's "List of the applications and of the corresponding
    # representative product" table. Does not exist in the 2018 batch.
    representative_product = "representative_product"
    share = "share"
    # Which broad end-use sector the application belongs to (EndUseSector). The
    # reports each use their own vocabulary, so this our mapping of those onto a small
    # set. A study decision, like the verdict beside it.
    sector = "sector"
    end_use_class = "end_use_class"
    reason = "reason"
    source_page = "source_page"


class EndUseSector(StrEnum):
    """Values of data/msa_end_use_info.csv's `sector`: the shared vocabulary the
    reports' own application labels are mapped onto.
    """

    construction = "construction"
    transport = "transport"
    industry_steel = "industry_steel"
    electronics_optics = "electronics_optics"
    batteries = "batteries"
    magnets = "magnets"
    chemicals_glass = "chemicals_glass"
    # Consumer goods, packaging, jewellery, and the reports' own "other"/"miscellaneous"
    other = "other"


class EndUseClass(StrEnum):
    """Values of data/msa_end_use_info.csv's `end_use_class`.

    Where MSA does not resolve a slice far enough to judge (aluminium's
    "Electrical engineering" is grid conductor, motors, transformers and
    appliances at once; cobalt's "Catalysts" is chemical and refining catalysts
    together, only the second of which is displaced) the slice stays `other`, which
    is an upper bound.
    """

    energy_transition = "energy_transition"
    transition_displaced = "transition_displaced"
    other = "other"
    # A grade the metal's tracked supply series does not cover, so it competes for
    # none of it. Excluded from charged_fraction, like the other two.
    off_grade = "off_grade"


class NedBasis(StrEnum):
    """Values of data/mineral_info.csv's `ned_basis`: where a metal's regional
    other-sector consumption level comes from. In descending confidence."""

    # The metal's own Material System Analysis chapter.
    msa = "msa"
    # An MSA chapter reporting the metal only inside a multi-element material, so
    # the level is split out with data/msa_element_composition.csv.
    msa_aggregate = "msa_aggregate"
    # No MSA coverage: a world series anchored at its last reported year, times the
    # metal-blind GDP share rules/allocation.smk grants the region of world supply.
    gdp = "gdp"


class MsaComposition(StrEnum):
    """Columns of data/msa_element_composition.csv: how one slice of one MSA
    material's end-use pie divides between the elements the material comprises.

    Only needed where an MSA material is not a single element. Shares run over
    every member element, tracked or not, so the mass this study charges nobody
    is visible rather than implied.
    """

    material = "msa_material"
    application = "application"
    element = "element"
    mass_share = "mass_share"
    reason = "reason"


class GdpProjection(StrEnum):
    """Columns of data/gdp_projection.csv: projected real GDP growth, as the rate
    reached in each reported year rather than a period average."""

    region = "region"
    year = "year"
    growth_percent = "potential_gdp_growth_percent"


class GdpIndex(StrEnum):
    """Columns of build/non_energy_demand/gdp_index.csv: the study region's real
    GDP relative to the splice year, one row per year."""

    year = "year"
    gdp_index = "gdp_index"
    # Whether the year is observed or projected, so a figure can mark the join.
    observed = "observed"


class NedLevel(StrEnum):
    """Columns of build/non_energy_demand/ned_levels.csv: the region's annual
    other-sector consumption of a metal at its anchor year, and what it was built
    from.

    The quantities behind the level are carried alongside it so a row can be
    checked against the report without opening the CSV it came from.
    """

    metal = "metal"
    basis = "basis"
    confidence = "confidence"
    # The year the level is measured at, which the GDP index is taken relative to.
    anchor_year = "anchor_year"
    level_kt = "level_kt"

    # An MSA-basis row: the chapter, what it reported, and the narrowing applied.
    msa_material = "msa_material"
    reference_consumption = "reference_consumption"
    unit = "unit"
    reference_region = "reference_region"
    # Share of the material's reference consumption charged to this metal: the
    # `other` slices of its end-use pie, times this element's share of each.
    charged_fraction = "charged_fraction"
    region_scale = "region_scale"

    # A gdp-basis row: the world series anchored on, and the metal-blind share.
    world_anchor_source = "world_anchor_source"
    world_demand_kt = "world_demand_kt"
    study_share = "study_share"


class NonEnergyDemand(StrEnum):
    """Columns of the non-energy demand tables of rules/ned.smk."""

    metal = "metal"
    year = "year"
    basis = "basis"
    confidence = "confidence"
    anchor_year = "anchor_year"
    level_kt = "level_kt"
    demand_kt = "non_energy_demand_kt"
    total_demand_kt = "total_non_energy_demand_kt"


class CarrierInfo(StrEnum):
    """Fields of pypsa.carriers.<carrier> in the config: where in a solved network
    that carrier's quantities are read off. See the block comment on
    `pypsa.carriers` in config/default.yaml for what each one means."""

    component = "component"
    measures = "measures"
    electricity_bus = "electricity_bus"
    note = "note"


class Component(StrEnum):
    """Values of pypsa.carriers.<carrier>.component: the PyPSA component the
    carrier lives on. The component decides which attributes exist, and a carrier
    name alone does not identify one (`gas` is both a Generator and a Store)."""

    generator = "Generator"
    link = "Link"
    line = "Line"
    storage_unit = "StorageUnit"
    store = "Store"


class Measure(StrEnum):
    """Values of pypsa.carriers.<carrier>.measures: which quantity to read off the
    network, and by which route."""

    # GW at the port touching an electricity bus, via n.statistics(bus_carrier=...).
    power = "power"
    # TWh, via the same call with storage=True.
    energy = "energy"
    # GW read straight off s_nom/p_nom, for components whose statistics ports cancel.
    rated_capacity = "rated_capacity"
    # km and GW-km from the component's `length`.
    route_length = "route_length"


class ElectricityBus(StrEnum):
    """Values of pypsa.carriers.<carrier>.electricity_bus: which port of a Link the
    electricity bus attaches to. bus0 is the input port, where n.statistics reports
    capacity negative -- so this is also what decides the sign flip."""

    bus0 = "bus0"
    bus1 = "bus1"


class SummaryColumn(StrEnum):
    """Columns of the network summaries (build/pypsa/summaries/*.csv) and hence the
    data variables of build/pypsa/all_scenarios.nc. Which of them a row carries
    follows from the measures its carriers declare; the rest are left empty."""

    expanded_capex = "expanded_capex_bn€"
    opex = "opex_bn€"

    brownfield_cap_gw = "brownfield_cap_gw"
    final_cap_gw = "final_cap_gw"
    expanded_cap_gw = "expanded_cap_gw"

    brownfield_cap_twh = "brownfield_cap_twh"
    final_cap_twh = "final_cap_twh"
    expanded_cap_twh = "expanded_cap_twh"

    # Route length is a property of the topology, not of the solve: PyPSA reinforces
    # existing corridors rather than adding new ones, so there is one column, not a
    # brownfield/final/expanded triple. Reinforcement shows up in the GW-km columns.
    route_length_km = "route_length_km"
    brownfield_capacity_length_gwkm = "brownfield_capacity_length_gwkm"
    final_capacity_length_gwkm = "final_capacity_length_gwkm"
    expanded_capacity_length_gwkm = "expanded_capacity_length_gwkm"


class CapacitySource(StrEnum):
    """Values of technology_info.<technology>.capacity_source: which build stage
    supplies the quantity a technology's mineral intensity is multiplied by."""

    # Expanded capacity over the window, from the pypsa summary (GW or TWh).
    pypsa_eur = "pypsa_eur"
    # Capacity-equivalent km of line/cable, from rules/grid.smk.
    grid = "grid"
    # EVs sold over the window x pypsa's per-vehicle battery size (MWh).
    ev_batteries = "ev_batteries"
    # EVs sold over the window (a per-unit dataset).
    ev_fleet = "ev_fleet"


class GridCarrier(StrEnum):
    """The three PyPSA carriers that make up the grid, and keys of pypsa.carriers
    in the config. Named here so code that reaches into a network by carrier
    (`forward_dc_links`) does not spell the string itself.

    Which derivation turns a grid technology's quantity into km is GridType, not
    this: a carrier is where the quantity is read off, not how it becomes a length.
    """

    ac = "AC"
    dc = "DC"
    distribution = "electricity distribution grid"


class GridType(StrEnum):
    """Values of technology_info.<technology>.grid_type: which of the three grid
    derivations a technology's km comes from.

    Not the same thing as its PyPSA carrier, though the two line up one-to-one:
    the carrier says where in the network the modelled quantity is read off,
    grid_type says how that quantity becomes a length. Each is estimated by its own
    rule in rules/grid.smk, writing build/grid/capacity_km/<grid_type>.csv.
    """

    hv_ac = "hv_ac"
    dc = "dc"
    distribution = "distribution"


class GridParameterColumn(StrEnum):
    """The one column data/grid_parameters.csv adds to ScalarTable: which of the
    three grid derivations consumes the row. Documentation only -- no rule reads
    it -- but checked with the rest so the table cannot lose it unnoticed."""

    grid_type = "grid_type"


class GridParameter(StrEnum):
    """The `parameter` rows of data/grid_parameters.csv.

    Both are numbers a human read off a page, so they cannot be re-derived by a
    rule the way the rest of the grid arithmetic is; they live in data/ rather than
    in the config because that is where this repo keeps transcribed literature. The
    hv_ac derivation needs no such number -- it is measured end to end on the
    networks -- so there is no third member.
    """

    # Rating of the HVDC bipole the ecoinvent HVDC cable inventories describe.
    # PyPSA expands HVDC as a capacity, so expanded GW-km only becomes km of cable
    # once a per-cable rating is assumed; this is that assumption.
    hvdc_reference_gw = "hvdc_reference_gw"
    # Route-km of the existing European distribution network, all voltage levels
    # below HV transmission. PyPSA's distribution link has no length, so its
    # modelled capacity growth can only become km by scaling this stock.
    distribution_existing_km = "distribution_existing_km"


class GridCapacity(StrEnum):
    """The columns every grid-length table shares: the capacity-equivalent length
    of line and cable one grid technology carries in one system scenario.

    build/grid/capacity_km/<grid>.csv carries these plus that grid's own
    derivation columns (AcGridKm / DcGridKm / DistributionGridKm); collected into
    build/grid/grid_capacity_km.csv, which is these three alone."""

    scenario = "scenario"
    technology = "technology"
    # The added capacity expressed as km of reference-rated line/cable, not a count
    # of new geographic route; see each estimate_*_grid_km script for its derivation.
    capacity_km = "capacity_km"


class HvAcGridKm(StrEnum):
    """Derivation columns of build/grid/capacity_km/hv_ac.csv: the fractional GW-km
    growth of the clustered AC network, and the real stock it is applied to."""

    # Circuit-km of the full-resolution AC network -- the real stock the fractional
    # expansion is applied to. Clustering collapses the true circuit-km, so the
    # clustered length cannot stand in for it.
    circuit_km_full = "circuit_km_full"
    brownfield_gwkm = "brownfield_gwkm"
    expanded_gwkm = "expanded_gwkm"
    expansion_ratio = "expansion_ratio"


class DcGridKm(StrEnum):
    """Derivation columns of build/grid/capacity_km/dc.csv: expanded GW-km,
    de-clustered, over the rating of the cable the inventory describes."""

    expanded_gwkm = "expanded_gwkm"
    # GW-km of the DC links that exist today, measured on both reference networks:
    # the two sides the clustering correction is the ratio of.
    existing_gwkm_full = "existing_gwkm_full"
    existing_gwkm_clustered = "existing_gwkm_clustered"
    # Full-resolution over clustered. Below 1: clustered centroid-to-centroid
    # lengths overshoot the real routes.
    clustering_correction = "clustering_correction"
    # data/grid_parameters.csv:hvdc_reference_gw, carried so a row explains its own
    # division.
    reference_gw = "reference_gw"


class DistributionGridKm(StrEnum):
    """Derivation columns of build/grid/capacity_km/distribution.csv: the growth of
    the modelled distribution rating over today's, applied to the existing stock."""

    # Peak of the exogenous low-voltage load, the present-day counterpart of the
    # distribution link's rating (there is no brownfield capacity to read).
    present_gw = "present_gw"
    final_gw = "final_gw"
    growth = "growth"
    # data/grid_parameters.csv:distribution_existing_km, carried for the same reason as
    # above.
    existing_km = "existing_km"


class HvdcSubseaShare(StrEnum):
    """Columns of build/grid/hvdc_subsea_share.csv: the measured subsea share of
    new DC build, the measurement grid_dc's frozen subsea/land market split in
    data/market_share_scenarios.csv is a rounding of."""

    scenario = "scenario"
    # New DC capacity-length gained in the solve, subsea-weighted and in total.
    expanded_gwkm = "expanded_gwkm"
    subsea_gwkm = "subsea_gwkm"
    subsea_share = "subsea_share"


class SystemNetwork(StrEnum):
    """Columns of build/pypsa/system_networks.csv: each solved network, the
    scenario standing for it, and whether it is the reference."""

    scenario = "scenario"
    nice_name = "nice_name"
    network = "network"
    reference = "reference"


class CountryInfo(StrEnum):
    """Columns of data/country_info.csv: every country the study region or the
    EU-27 reference region is built from, and its entity name in the OWID
    indicator table (which is keyed by name, not by ISO code)."""

    code = "country_code"
    owid_entity = "owid_entity"
    eu27 = "eu27"


class Indicator(StrEnum):
    """The national indicators the allocation principles are built on. The column
    each one is read from lives in sources_info.json (owid_indicators.columns), so
    these names stay independent of the source's own spelling."""

    population = "population"
    gdp = "gdp"
    energy = "energy"


class AllocationRegion(StrEnum):
    """The three regions the allocation factors are computed over: the EU-27 the
    published shares describe, the country set this study models, and the world
    both are shares of."""

    eu27 = "eu27"
    study = "study"
    world = "world"


class AllocationMethod(StrEnum):
    """Rows of data/allocation_factors_eu.csv: the three principles Malmaeus et al.
    (2025) Table 3 allocates globally available metal by."""

    gdp = "gdp"
    per_capita = "per_capita"
    per_capita_energy_corrected = "per_capita_energy_corrected"


class AllocationFactor(StrEnum):
    """Columns of data/allocation_factors_eu.csv (the first three) and of
    build/allocation/allocation_factors.csv (all of them). study_share is the one
    downstream rules multiply a global supply by; the `_owid` columns are the same
    shares recomputed from the indicator table, carried as a cross-check."""

    method = "allocation_method"
    source_label = "source_label"
    eu_share = "eu_share"
    eu_share_owid = "eu_share_owid"
    scale_eu_to_study = "scale_eu_to_study"
    study_share = "study_share"
    study_share_owid = "study_share_owid"


class IndicatorScope(StrEnum):
    """Values of the `scope` column of build/allocation/allocation_indicators.csv:
    whether a row is one country or one of the regional totals summed from them."""

    country = "country"
    aggregate = "aggregate"


class AllocationIndicator(StrEnum):
    """Identifying columns of build/allocation/allocation_indicators.csv; the
    remaining columns are the Indicator members."""

    scope = "scope"
    key = "key"
    entity = "entity"
    eu27 = "eu27"
    in_study = "in_study"


class AllocatedQuantity(StrEnum):
    """Values of the `quantity` param of the allocate_* rules (rules/allocation.smk):
    which global per-metal table is being allocated to the study region. Each names
    the spec that says how that table is spelled (allocate_to_study_region.TABLES).
    """

    # build/supply/final_supply.csv -- the chosen window-integrated world supply.
    supply = "supply"


class AllocatedCube(StrEnum):
    """What an allocated cube (build/allocation/*_scaled.nc) adds to the flat global
    table it was built from: a second dimension, and along it the share applied and
    the principle's published name. The metal-keyed variables keep the names of the
    quantity they carry, which its own helper module defines. The strings match
    AllocationFactor's because the columns carry over unchanged."""

    method = "allocation_method"
    share = "study_share"
    label = "source_label"


class ScenarioType(StrEnum):
    """Values of scenarios.<scenario>.scenario_type: what kind of change a scenario
    makes to the reference world, and so what kind of decision it stands for.

    Separating the two is the point of Fig. 3 — reconfiguring the energy system
    and re-specifying the technologies it is built from are made by different
    people at different cost. `check_scenario_types` in rules/compare.smk derives
    the type from how a scenario is actually built and refuses a declaration that
    disagrees, so a future scenario doing both cannot be filed under one of them.
    """

    # The scenario every other one is measured against. Exactly one.
    reference = "reference"
    # A different system scenario: another pypsa network scenario, or an MGA run
    # pushed off the cost optimum.
    system = "system"
    # The same system scenario built out of different sub-technologies, i.e. a
    # different market share scenario.
    substitution = "substitution"


class ScenarioEffect(StrEnum):
    """Columns of build/compare/scenario_effects.csv (rules/compare.smk): what one
    scenario does to one metal, against the reference scenario.

    One row per (scenario, metal, allocation_method), the reference scenario
    excluded — it is the origin the deltas are taken from, so its own row would
    be zeros. `delta_supply_points` is the column the comparison rests on: kt
    divided by allocated supply, which is what makes a move on aluminium and a
    move on iridium the same size when they cost the same fraction of the ceiling.
    """

    scenario = "scenario"
    scenario_type = "scenario_type"
    metal = "metal"
    allocation_method = "allocation_method"

    # The quantities the deltas are built from, carried so a row can be checked.
    energy_demand_kt = "energy_demand_kt"
    energy_demand_base_kt = "energy_demand_base_kt"
    non_energy_demand_kt = "non_energy_demand_kt"
    allocated_supply_kt = "allocated_supply_kt"

    # What the scenario does. Negative is relief, positive is load.
    delta_kt = "delta_kt"
    delta_percent = "delta_percent"  # of this metal's reference energy demand
    delta_supply_points = "delta_supply_points"  # of allocated supply

    # Where the metal ends up, and where it started: every sector's demand over
    # allocated supply, the axis of Fig. 2b.
    total_over_supply = "total_over_supply"
    total_over_supply_base = "total_over_supply_base"

    # The same two with other-sector demand left out, i.e. the transition's own
    # demand against the whole allocated claim. The sensitivity twin of Fig. 3
    # colours by these: the deltas above are unchanged by the choice, since the
    # other-sector term is a constant per metal, so only where a scenario leaves
    # the metal moves.
    energy_over_supply = "energy_over_supply"
    energy_over_supply_base = "energy_over_supply_base"

    # How much of the metal's demand the transition is, i.e. the ceiling on what
    # any scenario here could ever remove.
    energy_share_of_demand_base_percent = "energy_share_of_demand_base_percent"

    # Whether the reference already overruns allocated supply for this metal —
    # under this principle, so a metal can be short under one and not another.
    # The summary is taken over these metals alone.
    short_at_base = "short_at_base"


class ScenarioSummary(StrEnum):
    """Columns of build/compare/scenario_summary.csv (rules/compare.smk): each scenario
    collapsed to what it is worth and what it costs, over the short metals alone.

    One row per (scenario, allocation_method), the reference excluded. Every
    quantity is in percentage points of allocated supply and summed across metals
    — which treats a point of aluminium and a point of iridium as equal, so read
    the totals as a screening score and Fig. 3b for what actually moved.
    """

    scenario = "scenario"
    scenario_type = "scenario_type"
    allocation_method = "allocation_method"

    # How many metals the summary was taken over, i.e. how many were short.
    metals_short = "metals_short"

    # Everything the scenario takes off the short metals, as a positive magnitude,
    # and everything it adds to them. A scenario does both.
    relief_supply_points = "relief_supply_points"
    load_supply_points = "load_supply_points"

    # The single metal the scenario treats worst, and by how much. Signed: negative
    # is a scenario that loads nothing at all, so even its worst-treated metal gains.
    worst_change_supply_points = "worst_change_supply_points"
    worst_change_metal = "worst_change_metal"

    # Counts over `material_points`, and how many short metals this one scenario
    # brings back under allocated supply by itself.
    metals_relieved = "metals_relieved"
    metals_loaded = "metals_loaded"
    metals_resolved = "metals_resolved"


class MetalCluster(StrEnum):
    """Values of MetalPosition.cluster: what a metal's position asks of policy.

    Fig. 2c colours by this, because the two axes and the trace between them are
    read for one thing — whether the shortfall is the energy system's to fix —
    and the answer is not a quadrant. It is a strict ladder, each rung tested
    against the *most* the modelled scenarios can do (the `*_combined` end, not the
    single-scenario one), so a metal is only filed one rung down where technology
    choice provably cannot reach it. Parity is 1 on every one of these ratios by
    construction, so the ladder needs no threshold of its own -- but it is keyed
    by allocation principle like everything else here, since a stricter claim on
    world supply moves metals down it.
    """

    # Claimable supply already covers every sector's demand at the reference.
    within_supply = "within_supply"
    # Short at the reference, and a feasible combination of scenarios closes it:
    # a technology-choice problem, and the study carries the choice.
    scenario_closed = "scenario_closed"
    # Still short when every scenario that composes is combined: the energy system
    # could in principle fit under the ceiling, but not with the scenarios here.
    scenario_short = "scenario_short"
    # Other-sector demand alone outruns allocated supply, so the metal is short
    # before the transition asks for any of it and no energy-system scenario of any
    # kind reaches it. Supply-side action or other-sector demand reduction.
    demand_floor_short = "demand_floor_short"


class MetalPosition(StrEnum):
    """Columns of build/compare/metal_positions.csv (rules/compare.smk): each metal
    placed on the two axes of the clustering figure, and traced from the reference
    scenario to the lowest demand the energy-system scenarios reach.

    One row per (metal, allocation_method) — the principle decides the supply the
    ratios are taken against, and none of them is preferred here. The `_percent`
    columns are already percentages and the bare ratios are ratios, so a notebook
    plots a column as it stands.
    """

    metal = "metal"
    allocation_method = "allocation_method"

    # What this position asks of policy (MetalCluster), read off the columns
    # below. Fig. 2c colours by it.
    cluster = "cluster"

    # The two ends of the trace: the reference scenario, and the scenario that
    # leaves this metal with the least energy-system demand. Which scenario that
    # is differs per metal, so the reduced end is an envelope over the scenario
    # set, not one coherent world. `raised_scenario` is the other end of that
    # envelope, the scenario leaving the metal with the most; Fig. 2 traces to
    # the reduced end alone, Fig. 1b draws the whole span.
    base_scenario = "base_scenario"
    reduced_scenario = "reduced_scenario"
    raised_scenario = "raised_scenario"

    # The quantities the ratios are built from, carried so a row can be checked.
    energy_demand_base_kt = "energy_demand_base_kt"
    energy_demand_reduced_kt = "energy_demand_reduced_kt"
    energy_demand_raised_kt = "energy_demand_raised_kt"
    # The other reduced end: the least demand any feasible *combination* of scenarios
    # reaches, from build/compare/max_reduction.csv (rule build_max_reduction).
    # `reduced` is the best single scenario, so this is never above it.
    energy_demand_combined_kt = "energy_demand_combined_kt"
    non_energy_demand_kt = "non_energy_demand_kt"
    allocated_supply_kt = "allocated_supply_kt"

    # Energy-system demand alone against allocated supply. Over 100%: the
    # transition on its own outruns the share of world supply this principle grants.
    energy_over_supply_base_percent = "energy_over_supply_base_percent"
    energy_over_supply_reduced_percent = "energy_over_supply_reduced_percent"

    # Every sector's demand against allocated supply. Over 1: a shortfall.
    total_over_supply_base = "total_over_supply_base"
    total_over_supply_reduced = "total_over_supply_reduced"
    total_over_supply_raised = "total_over_supply_raised"
    total_over_supply_combined = "total_over_supply_combined"

    # The two parts Fig. 1b stacks, on that same ratio axis, so the figure draws
    # columns rather than differencing them: what no modelled scenario reaches, and
    # what they do. They sum to total_over_supply_base. Above 1 on the floor
    # alone, the metal is short before the transition asks for any of it.
    non_energy_over_supply = "non_energy_over_supply"
    energy_over_supply_base = "energy_over_supply_base"

    # The scenario span on that same floor-less reading, the two ends matching
    # total_over_supply_reduced/raised. The strip of the energy-only twin of
    # Fig. 3 is drawn from them.
    energy_over_supply_reduced = "energy_over_supply_reduced"
    energy_over_supply_raised = "energy_over_supply_raised"

    # How much of the region's total demand for the metal the energy transition
    # is, i.e. how much of the problem the modelled scenarios can reach at all.
    energy_share_of_demand_base_percent = "energy_share_of_demand_base_percent"
    energy_share_of_demand_reduced_percent = "energy_share_of_demand_reduced_percent"
    energy_share_of_demand_combined_percent = "energy_share_of_demand_combined_percent"

    # The trace's length in demand terms: the fraction of reference energy-system
    # demand the best scenario removes, and the fraction the best combination of
    # scenarios removes (Fig. 2b traces the first, Fig. 2c the second).
    scenario_percent = "scenario_percent"
    combined_scenario_percent = "combined_scenario_percent"

    # Where this principle's parity sits once the figure has divided by the
    # reference principle's supply — a horizontal line, the same for every metal,
    # which is what lets one scatter carry all three principles.
    parity_level_percent = "parity_level_percent"
    parity_level_ratio = "parity_level_ratio"


MAX_REDUCTION_SCENARIO = "max_reduction"

# What joins the scenario keys inside MaxReduction.substitution_scenarios: a
# combination is several scenarios in one cell, and the cell is still one field.
SCENARIO_SEPARATOR = ";"


class MaxReduction(StrEnum):
    """Columns of build/compare/max_reduction.csv (rules/compare.smk): the
    combination of scenarios leaving each metal with the least energy-system demand.
    """

    metal = "metal"

    # The combination, and how many decisions it is.
    system_scenario = "system_scenario"
    substitution_scenarios = "substitution_scenarios"
    scenario_count = "scenario_count"

    # The quantities the percentages are built from, carried so a row can be checked.
    energy_demand_base_kt = "energy_demand_base_kt"
    energy_demand_single_kt = "energy_demand_single_kt"
    energy_demand_combined_kt = "energy_demand_combined_kt"
    single_scenario = "single_scenario"

    # What the combination removes, and what one scenario alone removes, both as a
    # fraction of reference energy-system demand; and the difference between
    # them, which is what combining buys.
    reduction_percent = "reduction_percent"
    single_reduction_percent = "single_reduction_percent"
    extra_reduction_percent = "extra_reduction_percent"


class MineralGroup(StrEnum):
    """Keys of the `group` column in data/mineral_info.csv, named and coloured by
    the config's `mineral_groups`. Helper rows are supply-side hosts/aggregates,
    excluded from the LCI mineral list."""

    grid_conductor = "grid_conductor"
    battery = "battery"
    magnet_rees = "magnet_rees"
    # The metals that do the absorbing in a PV cell: Ga and Ge, and the thin-film
    # four (Te/In/Se/Cd) that CdTe and CIGS are made of.
    solar_semiconductor = "solar_semiconductor"
    # The PEM catalyst metals: iridium anode, platinum cathode, one PGM ore body.
    h2_pgm_catalysts = "h2_pgm_catalysts"
    # Metals no one technology is built around: the steel alloying metals (Mn, Mo,
    # Nb, Ni, V) and the contact and solder metals (Ag, Sn).
    dual_use = "dual_use"
    helper = "helper"


class PolicyScreen(StrEnum):
    """Columns of data/metal_screen_policy.csv: Annex II of Regulation (EU)
    2024/1252 (the Critical Raw Materials Act), one row per listed raw material,
    transcribed from data/source/EU_2024_1252.pdf. All 34 rows are transcribed;
    the screen admits the Annex I subset (see metal_helpers.policy_metals).
    """

    raw_material = "raw_material"
    designation = "designation"
    annex_i_wording = "annex_i_wording"
    minerals = "minerals"
    technology = "technology"
    note = "note"


class PolicyDesignation(StrEnum):
    """Values of data/metal_screen_policy.csv's `designation`. Annex I is a subset
    of Annex II, so the two are ordered: `strategic` implies `critical`.
    """

    # Annex II only: transcribed for the record, does not admit.
    critical = "critical"
    # Annex I, which is the policy screen.
    strategic = "strategic"


class MetalExclusion(StrEnum):
    """Columns of data/metal_excluded.csv: metals this study looked at and left
    out on purpose.
    """

    metal = "metal"
    considered_because = "considered_because"
    reason = "reason"


class LiteratureScreen(StrEnum):
    """Columns of build/metals/literature_screen.csv: energy-transition-led demand
    against primary production capacity, per metal, from Bieuville et al. 2026.

    Named for its provenance rather than its verdict. The ratio is an exposure
    measure -- how much of a metal's world primary capacity the transition lays
    claim to -- and at the threshold used it is nowhere near a statement that the
    metal runs out; the shortage verdict is the study's own, in rules/compare.smk.
    What the screen mostly contributes is the source's own choice of which metals
    to model at all.
    """

    # The source's own spelling of the metal, which is the key
    # data/mineral_info.csv's bieuville_name joins a study metal to.
    bieuville_name = "bieuville_name"

    # The quantities the screen is derived from, kept so the ratio is checkable
    # rather than asserted.
    total_demand_t = "total_demand_t"
    other_sector_demand_t = "other_sector_demand_t"
    transition_demand_t = "transition_demand_t"
    primary_capacity_t = "primary_capacity_t"

    # The screen itself: what the transition asks for over what can be produced.
    demand_over_capacity = "demand_over_capacity"
    # Not a criterion: how much of the metal's total demand the transition is,
    # i.e. how much of the pressure the scenarios in this study could ever reach.
    transition_share = "transition_share"


class MetalSelection(StrEnum):
    """Columns of build/metals/selection.csv: one row per candidate metal, what
    each screen says about it, and whether data/mineral_info.csv agrees.

    The union of the two screens is the study's metal list. This file is the audit
    of that claim, not its source -- data/mineral_info.csv stays the single gate
    (see rules/metals.smk).
    """

    metal = "metal"

    passes_policy = "passes_policy"
    # `strategic` for every admitted metal; blank otherwise.
    designation = "designation"
    policy_raw_material = "policy_raw_material"
    technology = "technology"

    passes_literature = "passes_literature"
    demand_over_capacity = "demand_over_capacity"
    transition_share = "transition_share"

    # Union of the screens, and what the repository actually does.
    selected = "selected"
    in_study = "in_study"
    excluded_on_purpose = "excluded_on_purpose"
    exclusion_reason = "exclusion_reason"
    # Blank where selection and study agree; otherwise what disagrees, which is
    # what the rule raises on.
    disagreement = "disagreement"


class ThresholdSensitivity(StrEnum):
    """Columns of build/metals/threshold_sensitivity.csv: which metals the
    literature screen admits at each threshold tested.
    """

    threshold = "threshold"
    metal = "metal"
    demand_over_capacity = "demand_over_capacity"
    passes_literature = "passes_literature"
    # Whether the union still selects the metal at this threshold -- a metal on
    # the policy list stays in however the literature cut moves.
    selected = "selected"
    in_study = "in_study"
