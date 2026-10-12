# Manually transcribed sources

`sources_info.json` configures the sources that scripts parse programmatically (`OWID minerals parquet`, `OWID World Bank GDP`, `IEA_Critical_Minerals_Dataset_2026.xlsx`, `Lundaev_2023_SM.xlsx`, `schlichenmaier_2022.xlsx`, `bieuville_2026_SI_2`). This file covers the rest: values a human read off a page and typed into a CSV, which cannot be re-derived by re-running the workflow.

Page numbers are PDF page numbers, not the printed footer numbers.

## Documents

Every source below is cited by its file name in the rest of this file. Only the
three CC BY 4.0 workbooks the workflow reads ship with the repo; every other document
is copyright of its publisher and is obtained from its link.
`bieuville_2026_SI_2.xlsx` is also read by the workflow, so download it (Supplementary
Data 2 of the article) and save it as `data/source/bieuville_2026_SI_2.xlsx` before a run.

| File | Reference | Link |
|---|---|---|
| `IEA_Critical_Minerals_Dataset_2026.xlsx` (included, CC BY 4.0) | IEA, *Critical Minerals Data Explorer*, Paris, 2026 edition | <https://www.iea.org/data-and-statistics/data-tools/critical-minerals-data-explorer> |
| `Lundaev_2023_SM.xlsx` (included, CC BY 4.0) | Supplementary material to V. Lundaev, A.A. Solomon, T. Le, A. Lohrmann & C. Breyer, *Review of critical materials for the energy transition, an analysis of global resources and production databases and the state of material circularity*, Minerals Engineering 203 (2023) 108282 | <https://doi.org/10.1016/j.mineng.2023.108282> |
| `schlichenmaier_2022.xlsx` (included, CC BY 4.0) | Supplementary data to S. Schlichenmaier & T. Naegler, *May material bottlenecks hamper the global energy transition towards the 1.5 °C target?*, Energy Reports 8 (2022) 14875–14887 | <https://doi.org/10.1016/j.egyr.2022.11.025> |
| `bieuville_2026_SI_2.xlsx` (download) | Supplementary Data 2 to P. Bieuville, G. Majeau-Bettez & A. de Bortoli, *Technology flexibility and sobriety to address shortage of energy-transition metals*, Nature Sustainability 9 (2026) 419–430 | <https://doi.org/10.1038/s41893-025-01762-y> |
| `IEA_2022.pdf` | IEA, *The Role of Critical Minerals in Clean Energy Transitions*, World Energy Outlook Special Report, Paris, 2021 (revised March 2022) | <https://www.iea.org/reports/the-role-of-critical-minerals-in-clean-energy-transitions> |
| `IEA_2024.pdf` | IEA, *Batteries and Secure Energy Transitions*, Paris, 2024 | <https://www.iea.org/reports/batteries-and-secure-energy-transitions> |
| `International Energy Agency - 2026 - Global Critical Minerals Outlook 2026.pdf` | IEA, *Global Critical Minerals Outlook 2026*, Paris, 2026 | <https://www.iea.org/reports/global-critical-minerals-outlook-2026> |
| `carrara_2020.pdf` | S. Carrara, P. Alves Dias, B. Plazzotta & C. Pavel, *Raw materials demand for wind and solar PV technologies in the transition towards a decarbonised energy system*, JRC, EUR 30095 EN (2020) | <https://doi.org/10.2760/160859> |
| `WNA_2025.pdf` | World Nuclear Association, *World Nuclear Performance Report 2025*, Report No. 2025/002 | <https://world-nuclear.org/our-association/publications/global-trends-reports/world-nuclear-performance-report> |
| `enagas_2025.pdf` | Enagás Hydrogen Technology Observatory, *Renewable hydrogen production via electrolysis: state-of-the-art and future prospects*, December 2025 | <https://www.enagas.es/en/energy-transition/hydrogen-network/green-hydrogen/technology-observatory/> |
| `wei_2025.pdf` | Wei et al., *Navigating energy transition solutions for climate targets with minerals constraint*, Nature Climate Change 15 (2025) 833–841 | <https://doi.org/10.1038/s41558-025-02373-3> |
| `eurelectric_2020.pdf` | Eurelectric, *Distribution Grids in Europe: Facts and Figures 2020* | <https://www.eurelectric.org/publications/distribution-grids-in-europe-facts-and-figures-2020/> |
| `malmaeus_2025.pdf` | J.M. Malmaeus, E.C. Alfredsson & E. Lindblom, *On the allocation of critical metals between nations for a green and just transition*, Environmental Development 54 (2025) 101157 | <https://doi.org/10.1016/j.envdev.2025.101157> |
| `itten_2014.pdf` | R. Itten, R. Frischknecht & M. Stucki, *Life Cycle Inventories of Electricity Mixes and Grid*, v1.3, treeze Ltd., Uster, for the Paul Scherrer Institut (2014) | |
| `JRC143190.pdf` | European Commission, Joint Research Centre, *Material requirements for electricity grids*, JRC143190 (2025) | <https://publications.jrc.ec.europa.eu/repository/handle/JRC143190> |
| `gerloff_2021.pdf`, `gerloff_2021_SI.docx` | N. Gerloff, *Comparative Life-Cycle-Assessment analysis of three major water electrolysis technologies while applying various energy scenarios for a greener hydrogen production*, Journal of Energy Storage 43 (2021) 102759, and its supplementary information | <https://doi.org/10.1016/j.est.2021.102759> |
| `Månberger and Stenqvist - 2018 - Global metal flows in the renewable energy transition.pdf` | A. Månberger & B. Stenqvist, *Global metal flows in the renewable energy transition: exploring the effects of substitutes, technological mix and development*, Energy Policy 119 (2018) 226–241 | <https://doi.org/10.1016/j.enpol.2018.04.056> |
| `nassar_2022_SI.pdf` | Supporting information to N.T. Nassar, G.W. Lederer, J.L. Brainard, A.J. Padilla & J.D. Lessard, *Rock-to-metal ratio: a foundational metric for understanding mine wastes*, Environmental Science & Technology 56 (2022) 6710–6721 | <https://doi.org/10.1021/acs.est.1c07875> |
| `EU_2024_1252.pdf` | Regulation (EU) 2024/1252 of 11 April 2024 (Critical Raw Materials Act), consolidated text 02024R1252 — 03.05.2024 | <http://data.europa.eu/eli/reg/2024/1252/oj> |
| `MSA_2018.pdf` | F. Passarini, L. Ciacci, P. Nuss & S. Manfredi, *Material Flow Analysis of Aluminium, Copper, and Iron in the EU-28*, JRC, EUR 29220 EN (2018) | <https://doi.org/10.2760/1079> |
| `MSA_2020_batteries.pdf` | C.T. Matos et al., *Material System Analysis of five battery-related raw materials: Cobalt, Lithium, Manganese, Natural Graphite, Nickel*, JRC, EUR 30103 EN (2020) | <https://doi.org/10.2760/519827> |
| `MSA_2021_nine.pdf` | C.T. Matos et al., *Material System Analysis of Nine Raw Materials: Barytes, Bismuth, Hafnium, Helium, Natural Rubber, Phosphorus, Scandium, Tantalum, Vanadium*, JRC, EUR 30704 EN (2021) | <https://doi.org/10.2760/677981> |
| `MSA_2023.pdf` | In Extenso et al., *Update of the 2015 Material System Analyses*, final report, European Commission (2023) | <https://doi.org/10.2873/440874> |
| `EC_ageing_report_2024.pdf` | European Commission (DG ECFIN) & Economic Policy Committee, *The 2024 Ageing Report: Economic and Budgetary Projections for the EU Member States (2022-2070)*, European Economy Institutional Paper 279 | <https://doi.org/10.2765/022983> |

## `data/market_share_scenarios.csv`

Each cell is the market share of a sub-technology within its parent technology,
per scenario. Every `technology` group sums to 1.0.

### `Market share current` (base column)

The base-scenario share of each sub-technology within its parent technology. Each
row's value is sourced to one of the documents listed above:

| Source PDF | Rows it sets | Values |
|---|---|---|
| `IEA_2022.pdf` — *The Role of Critical Minerals in Clean Energy Transitions* | all `onshore_wind`, `offshore_wind` | DFIG/PMSG/EESG splits |
| | `grid_battery` NMC111, NMC532 | 0.1, 0.1 |
| | `ev_motor` | PM 0.9, induction 0.1 |
| `International Energy Agency - 2026 - Global Critical Minerals Outlook 2026.pdf`, p. 72 | all `ev_battery` | NMC111 0.03, NMC532 0.084, NMC622 0.35, NMC811 0.175, LFP 0.128, NCA 0.233 (see below) |
| `carrara_2020.pdf` — Carrara et al., *Raw materials demand for wind and solar PV* | all `utility_solar`, `rooftop_solar` | c-Si 0.954, CdTe 0.024, CIGS 0.019, a-Si 0.003 |
| `IEA_2024.pdf` — *Batteries and Secure Energy Transitions* | `grid_battery` LFP 0.8 | |
| `WNA_2025.pdf` — *World Nuclear Performance Report 2025* | `nuclear` PWR | 1.0 |
| `enagas_2025.pdf` — Enagás Hydrogen Technology Observatory, *Renewable hydrogen production via electrolysis: state-of-the-art* (Dec 2025), p. 29, reporting IEA electrolyser manufacturing capacity | all `h2_electrolysis` | AEC 0.75, PEM 0.22, SOEC 0.03 |

Rows with no source PDF:

- `ccgt` = 1.0 — this technology is inconsequential for metal use.
- `heat_pump` = 1.0 — single-sub-technology placeholder.

Notes on the transcription:

- `rooftop_solar` duplicates `utility_solar`
- `ev_battery` is the European Union's 2025 bar of *Share of electric vehicle battery
  sales by chemistry and region, 2023-2025*: sales shares by battery capacity of new
  EVs registered, two/three-wheelers excluded. The chart is vector; its segments measure
  low-nickel 0.114, high-nickel 0.758, LFP 0.128. The text on p. 71 gives the EU's LFP
  share as "almost 15%"; the chart's value is used, as it resolves all three classes.
- The chart resolves only those classes, so each is split in the proportions of the
  Europe LDV mix in `IEA_2022.pdf` (NMC111 0.07, NMC532 0.2, NMC622 0.3, NMC811 0.15,
  NCA 0.2):
  low-nickel (NMC333/442/532) → NMC111 7/27, NMC532 20/27; high-nickel (NMC622/721/811,
  NCA, NMCA) → NMC622 6/13, NMC811 3/13, NCA 4/13. LFP includes LMFP.

### Scenario columns

Each scenario is the base column with one technology's rows. Everything else is copied unchanged.

| CSV column | Rows overwritten |
|---|---|
| `EV battery Na-ion` | `ev_battery`: Na-ion → 1, rest → 0 |
| `EV battery NMC-811` | `ev_battery`: NMC811 → 1, rest → 0 |
| `EV battery LFP` | `ev_battery`: LFP → 1, rest → 0 |
| `Solar c-Si` | `utility_solar`/`rooftop_solar`: c-Si → 1, CdTe/CIGS/a-Si → 0 |
| `EV magnet pull` | `ev_motor`: induction → 1, PM → 0 |
| `Grid aluminium wiring` | `grid_hv_ac`/`grid_dc`/`grid_distribution`: each copper sub-technology → 0, its `(Al)` variant → the share the copper one had |
| `Wind magnet pull` | `onshore_wind`: GB-DFIG → 1, rest → 0; `offshore_wind`: GB-PMSG → 1, rest → 0 |
| `Electrolyser PEM-free` | `h2_electrolysis`: PEM → 0, AEC and SOEC → their base shares renormalised over the remaining 0.78 |

`Na-ion`, `NMC-811` and `LFP` have no IEA counterpart — they pin one chemistry to
1.0 as single-chemistry sensitivity probes, not projected market mixes.

`Solar c-Si` pushes both solar technologies onto crystalline silicon, which is the
substitution the literature proposes: `wei_2025.pdf` (Wei et al., *Navigating energy
transition solutions for climate targets with minerals constraint*, Nat. Clim.
Chang. 15, 833–841) identifies indium, cadmium and tellurium as the minerals most
often short across the IPCC AR6 pathways, thin-film PV being what puts them there,
and names "replacing thin-film PV with highly efficient crystalline silicon" as the
mitigation. Two side effects come with it: `carrara_2020` gives c-Si 1 kg/MW of
silver against thin-film's none, and `PV, CIGS` carries 9,700 kg/MW of copper against
c-Si's 3,700, so the scenario loads silver slightly and relieves copper slightly. The
tin penalty Wei et al. also warn of is **not** visible — `carrara_2020` reports no
tin for any PV type, so ribbon and solder are outside these intensities.

`Grid aluminium wiring` keeps every km split (subsea/land, HV/MV/LV) exactly as the
base column has it and changes only what the conductor is made of, so it is a pure
material scenario: see `data/grid_conductor_info.csv` below.

`Wind magnet pull` builds each siting's wind on the least permanent magnet that siting
allows: onshore, wound-rotor induction (GB-DFIG), which has no generator magnet;
offshore, the medium-speed hybrid drive (GB-PMSG), a single-stage gearbox with a
magnet about a third the mass of a direct drive's. Like every other substitution
column it is a technical ceiling, not a projection.

The split is what the siting allows. Onshore DFIG is a volume product (the base
column's 0.70 is IEA's observed share). Offshore it is not: it has precedent at 5–6 MW
and none at 15 MW, geared slip-ring machines being what access-constrained offshore
O&M pushed the industry away from. `carrara_2020` (p. 21) rules out both magnet-free
machines offshore, DD-EESG and GB-DFIG being "unsuitable for offshore installations in
future scenarios, because of their considerable weight", and names the hybrid drive as
the favoured alternative, citing a cut in neodymium "from 186 kg/MW installed capacity
to just 62 kg/MW" against a direct-drive permanent magnet.

DD-EESG would not relieve the magnet REEs on these intensities in any case. Carrara's
DD-EESG column stands in for DD-HTS as well, and its rare earths were "set equal to the
lower end of the other technologies" (p. 25) rather than inventoried: Dy 6 and Tb 1
kg/MW are GB-PMSG's exactly, and Nd 28 and Pr 9 match no other column. The rare earth
a machine without a generator magnet does carry is in the magnets that attach fixtures
inside the tower (p. 26), which is what GB-DFIG's Nd 12 and Dy 2 stand for. The base
column's 0.05 of onshore DD-EESG carries the placeholder values.

Both machines use less copper than the direct drive they displace — Cu 1,400 kg/MW
onshore and 950 offshore against DD-PMSG's 3,000 — so wind copper falls
1,737 → 1,198 kt. At `gdp` allocation the scenario relieves 98.8 points of allocated
supply on terbium, 58.0 on dysprosium, 23.0 on neodymium, 16.7 on praseodymium and
0.34 on copper; its one load is 0.05 points of aluminium. `EV magnet pull` trades the
other way, its rotor copper loading 3.9 points.

### Grid HVDC subsea/land split (`grid_dc`)

`Grid cable, HVDC subsea` 0.30 / `Grid cable, HVDC land` 0.70, constant across
scenarios. Not read off a page: it rounds a measurement on the model itself.
Weighting each DC corridor's PyPSA-Eur `underwater_fraction` by the GW·km it gains in
the base solve gives 25,225 / 82,836 = 30.5 %. km is GW·km over a single reference
rating (`hvdc_reference_gw`), so the km- and GW·km-weighted splits are equal and the
number serves directly as a market share.

The share drifts between scenarios (different corridors expand; each
`underwater_fraction` is fixed) and the static split ignores that. Defensible: the two
inventories differ ~3 % in the metals that survive (copper, aluminium — lead differs
more but is not a study mineral), so no headline number moves by 0.1 %. Rule
`measure_hvdc_subsea_share` recomputes it per scenario into
`build/grid/hvdc_subsea_share.csv`; the `grid_workflow` notebook plots it against 0.30.

### Grid distribution voltage-level split (`grid_distribution`)

PyPSA-Eur models everything below HV transmission as one link; this splits its km
across three ecoinvent CH datasets, constant across scenarios. The shares are the
relative km of the Swiss network each dataset is built from, read from the
`Technology:` line of its ecoinvent `comment` (2010 Swiss grid, tracing to Itten,
Frischknecht & Stucki 2014). Same datasets that supply the per-km intensities, so
weighting and intensities are consistent. Re-readable from the Brightway store
(`Database("ecoinvent-3.10-cutoff")`, project `metal-snapshots`).

| Sub-technology | ecoinvent dataset (CH) | Voltage | Cable + line | Share |
|---|---|---|---|---|
| `Grid line, HV AC` | transmission network construction, high voltage | >24 kV | 1 843 + 13 988 = 15 831 | 0.08 |
| `Grid line, MV` | transmission network construction, medium voltage | 1–24 kV | 29 629 + 13 042 = 42 671 | 0.23 |
| `Grid line, LV` | distribution network construction, low voltage | <1 kV | 115 926 + 12 720 = 128 646 | 0.69 |

(187 148 km total; the CH ">24 kV" dataset stands in for the 36–150 kV
sub-transmission level.) Distribution dominates grid copper and the three datasets
differ several-fold in it (HV 1 235, MV 2 471, LV 3 879 kg/km) — but the split is
insensitive at the level that matters, because real national splits weight it to
nearly the same copper:

| Split | HV | MV | LV | kg Cu/km |
|---|---|---|---|---|
| **Swiss ecoinvent (used)** | .08 | .23 | .69 | **3 344** |
| Germany (77 / 479 / 1 123 thousand km) | .046 | .285 | .669 | 3 356 |
| Italy, e-distribuzione (0.019 / 362 / 791) | .000 | .314 | .686 | 3 437 |
| Eurelectric, all Europe | .03 | .37 | .60 | 3 279 |

All within 3 % of the Swiss figure, so the stand-in is left as it is — it is also the
only one weighted consistently with the intensities it multiplies.

## `data/grid_parameters.csv`

The two quantities `rules/grid.smk` needs that the model cannot supply. Both are read
off a page, which is why they are here and not in a rule.

### `hvdc_reference_gw` = 0.7 GW

Rating of the bipole the ecoinvent HVDC cable inventories describe. PyPSA expands HVDC
as a capacity, so GW·km becomes km only via an assumed per-cable rating — and it must
be *this* cable's, since the inventory is per km of one specific design.

ecoinvent gives the design but not the rating: the subsea dataset's `comment` reads
*"The voltage level is assumed to be 450 kV. 2x790-mm² copper conductors,
mass-impregnated paper insulation, and steel and lead sheeting."* Both HVDC datasets
are modelled after Jorge, Hawkins & Hertwich (2012), *LCA of electricity transmission
and distribution — part 1*, Int J LCA 17: 9–15, whose subsea case is NorNed: 450 kV,
**700 MW**. Hence 0.7 GW — from the paper, not the database. (700 MW over ±450 kV is
778 A/pole, which 790 mm² copper carries comfortably, so the two are consistent.)

Caveat: the **land** dataset is 400 kV, a different cable, so strictly the two
sub-technologies do not share a rating. One rating is used because the km split
between them is itself GW·km-weighted and the inventories differ ~3 %.

### `distribution_existing_km` = 10 000 000 km

Route-km of the existing European distribution network. PyPSA's distribution link has
no length and no brownfield capacity, so km is only reachable by scaling this stock by
the link's modelled capacity growth — making it a direct multiplier on all
distribution metal demand, and the most consequential transcription in this file.

`eurelectric_2020.pdf` p.16 — Eurelectric, *Distribution Grids in Europe: Facts and
Figures 2020*: *"In Europe, DSOs connect around 300 million customers by operating 10
millions km of power lines and supplying around 2800 TWh of electricity per year."*
Country set is that page's Figure 3.3 axis: EU-27 less Malta, plus CH and UK — close
enough to the PyPSA-Eur set to use unscaled.

Attributed to *DSOs*, in a DSO-scoped report, under a figure titled "Share of distribution lines, per type". It does not overlap `grid_hv_ac`: the 3 % HV inside it is DSO sub-transmission (CENELEC HV >36 kV, so 36–150 kV), while PyPSA's `AC` carrier is
the 220–400 kV TSO grid.

## `data/allocation_factors_eu.csv`

**Table 3** (PDF page 6) of `malmaeus_2025.pdf` — J.M. Malmaeus, E.C. Alfredsson
& E. Lindblom, *On the allocation of critical metals between nations for a green
and just transition*, Environmental Development 54 (2025) 101157. The table is
three rows and one column ("EU"), transcribed verbatim except that the printed
percentages are stored as fractions and the row names are set in sentence case,
because the figures print them as labels (Table 3 writes the first "GDP Share"):

| `allocation_method` | `source_label` (Table 3 row) | Table 3 | `eu_share` |
|---|---|---|---|
| `gdp` | GDP share | 14.6 % | 0.146 |
| `per_capita` | Per capita share | 5.7 % | 0.057 |
| `per_capita_energy_corrected` | Per capita corrected for energy use | 3.3 % | 0.033 |

These are shares of the **globally available** amount of a critical metal that
the EU-27 could claim under each of three allocation principles (paper §2.2,
§3). The paper's own derivation, from ourworldindata.org accessed 2023-11-28:

- **GDP share** — the EU's share of the world economy. The paper reads this as
  *grandfathering*: allocation follows current economic activity.
- **Per capita share** — the EU's share of world population, i.e. *equality*.
- **Per capita corrected for energy use** — the per-capita share multiplied by
  (global per-capita energy use / regional per-capita energy use), so an
  energy-rich region is allocated less. Their footnote 2 gives 21 MWh/capita
  globally against 36 MWh/capita in the EU in 2022, a correction factor of 0.58.

## `data/grid_conductor_info.csv`

How much of each grid dataset's copper is conductor, and therefore how much of it
`build_conductor_substitution_db` may replace with aluminium. The remainder is
switchgear and earthing copper, which cannot be.

ecoinvent buys copper through a single lumped `market for copper, cathode` exchange
per dataset, so the split is not readable from the database. It *is* readable from the
inventory underneath it — the CH datasets are a row-for-row transcription of **Itten,
Frischknecht & Stucki (2014)**, *Life Cycle Inventories of Electricity Mixes and Grid*
(treeze/ESU, v1.3), Tab. 4.18, whose component tables give the conductor copper
separately.

| Sub-technology | Conductor share | Derivation |
|---|---|---|
| `Grid line, LV (Al)` | **1.0** | Tab. 4.5 (EWZ Zurich cable inventory): 4 600 kg Cu/km, 0 kg Al/km, all of it under "cable including insulation". Equals Tab. 4.18's LV copper exactly, so the network total is cable. |
| `Grid line, MV (Al)` | **0.914** | Tab. 4.6 underground cable 2 784 kg Cu/km over 29 629 km + Tab. 4.7 aerial line 2 330 kg Cu/km over 13 042 km = 2 645 kg/km against Tab. 4.18's 2 894 kg/km. The 249 kg/km gap is the HV/MV switching stations the dataset also covers. (The same weighting reproduces Tab. 4.18's aluminium, 2 200 kg/km, to 0.05 % — which is what confirms the lengths.) |
| `Grid line, HV AC (Al)` | **1.0** | Tab. 4.8, 150 kV underground cable, 8 600 kg Cu/km over 1 843 km = 1 001 kg/km, against Tab. 4.18's 1 001.2. The other 13 988 km is aerial line, which is ACSR and carries no copper at all. |
| `Grid cable, HVDC land (Al)` | **1.0** | ecoinvent itself: the copper exchange is commented *"Literature Value. for cable"* and is paired 1:1 with a `wire drawing, copper` exchange of identical mass. |
| `Grid cable, HVDC subsea (Al)` | **1.0** | As above. |

Note what the HV AC row means: the aluminium scenario converts the *underground*
portion of the HV network to aluminium. The overhead portion is aluminium already, so
that grid moves least — 1 001 kg Cu/km against LV's 4 600.

## `data/conductor_areas.csv`

The two conductor cross sections whose ratio, weighted by the densities in
`data/metal_densities.csv`, is the **0.477 kg of aluminium per kg of copper** that
`build_conductor_substitution_db` substitutes at. Stated as the two areas rather than
as the ratio, so the engineering claim rather than its arithmetic is what is on record.

`JRC143190.pdf` — European Commission JRC (2025), *Material requirements for
electricity grids*, Table 2: a land/submarine cable inventory given twice, once with a
**4 750 mm² aluminium** and once with a **3 000 mm² copper** conductor, *"because they
are comparable in terms of resistance"*. Those areas are 12.8 vs 26.9 kg/m, a mass
ratio of 0.477. The first-principles equal-resistance figure (resistivity × density) is
0.49, so the two agree; JRC's is used because it is an explicit engineering pairing
rather than a textbook idealisation.

The same table cross-checks the *direction*: swapping copper for aluminium leaves the
polymer, lead and steel layers of the cable untouched, which is what the derived
datasets do.

Scenario framing follows Ushie et al. (2025), *Sustainable Energy Research* 12:56
(doi:10.1186/s40807-025-00178-8), whose "wider use of aluminium in underground cables"
(WAC) scenario is the same one.

## `data/bill_of_materials.csv`

Mass per MW of capacity, one row per (sub-technology, part, material), from two sources.
Which database activity supplies each material is a separate decision, in
`data/bom_material_info.csv`.

### Wind and PV — `carrara_2020.pdf`

S. Carrara, P. Alves Dias, B. Plazzotta and C. Pavel, *Raw materials demand for wind and
solar PV technologies in the transition towards a decarbonised energy system*, JRC (2020),
doi:10.2760/160859.

Wind is Table 2 (*Material usage estimates in t/GW for different wind turbine types*) as
printed, which is 2018 and carries no scenario split; t/GW is kg/MW. PV is Table 4, which
is resolved by scenario and year: **the MDS (Medium Demand Scenario) column for 2030 is
taken**, MDS being the report's baseline and 2030 the premise background year
(`lci.premise_scenario.year`). LDS and HDS are not used. PV's foreground is therefore
projected, while wind and the electrolysers, which have no 2030 values, are measured. MDS
is still a choice for CdTe and CIGS, whose intensities Table 4 spreads widely across
LDS / MDS / HDS.

Table 4's `All` rows — frame, mounting and general wiring, common to every panel type —
are the `structure` part of all four PV sub-technologies, and the technology-specific rows
the `cell` part. CIGS therefore carries copper twice, 4500 kg/MW of structure and 15 kg/MW
of absorber, as Section 3.5 says to.

**Carrara's chromium, manganese, molybdenum and nickel rows are not transcribed.** They are
the alloy content of the steel the same table lists, and that steel is bought: the implied
fractions (Mn 0.66%, Mo 0.09%, Ni 0.28% of the steel mass) are a low-alloyed grade rather
than a stainless one, and `market for steel, low-alloyed` carries those elements itself.
Table 2's `Iron (cast)` row is transcribed, as cast iron.

Boron is not transcribed: ecoinvent 3.10 carries no boron product a magnet maker buys —
no ferroboron, and boron carbide is an abrasive — so Table 2's 0–6 t/GW cannot be bought
without inventing a supply chain. Boron is not tracked; `data/metal_excluded.csv` records it.

Table 2's `Glass/carbon composites` is taken as all glass fibre. The report gives no split,
only that glass fibre "does not exceed 88%" with up to 12% carbon fibre in next-generation
turbines, which is a bound on a future design rather than a 2018 value.

### Electrolysers — `gerloff_2021.pdf` / `gerloff_2021_SI.docx`

N. Gerloff, *Comparative Life-Cycle-Assessment analysis of three major water electrolysis
technologies while applying various energy scenarios for a greener hydrogen production*,
Journal of Energy Storage 43 (2021) 102759.

Read off the SI's Figs. 1–5 (*Values and ecoinvent processes of the 1 MW AEC / PEMEC / SOEC
system*), which give each component's material and mass for a 1 MW plant. Stack components
are scaled from 1 kW with an exponent of 0.88 and balance-of-plant components with 0.7, as
Section 2.1.4 describes; the transcription takes the 1 MW values as printed.

The **forming processes** (sheet rolling, wire drawing, welding, injection moulding, screen
printing) are not transcribed: each is listed against the same mass as the material process
beside it and carries no material of its own.

Concrete is the one row given as a volume. PEMEC and SOEC print both (5600 kg == 2.3 m³),
AEC only the volume (7.7 m³), so the AEC mass is that volume at the report's own implied
2434.8 kg/m³.

Gerloff models the KOH electrolyte as an operating consumable (0.0037 kg per kg H₂), not a
stock in the plant, so it is not in the bill.

## `data/bom_material_info.csv`

Which activity of the premise database each material is bought from, and how much of it one
kg of that material is. The study's own mapping rather than transcription: Gerloff names
ecoinvent 3.5 processes, several of which 3.10 has split or renamed, and Carrara names none
at all. The basis of each row is in the CSV.

Each material takes the most regionally specific market the database offers — the IAM's
Western Europe region where premise regionalises the market (`steel, low-alloyed`), its
`World` market where that is the only one premise wrote (the metals its own module adds,
including iridium and germanium, which ecoinvent 3.10 has no product for), and ecoinvent's
European or global market where premise wrote neither. The CH `market for concrete, normal
strength` is the one the ecoinvent grid datasets buy.

`activity_per_kg` is 1 but for two cases: concrete, where the market sells m³; and
Carrara's four magnet REEs, reported as the element where the market sells the oxide. Those
fractions are checked against each dataset's own in-ground flow, which is how ecoinvent's
`praseodymium oxide` and `terbium oxide` were found to be Pr₂O₃ and Tb₂O₃ rather than the
Pr₆O₁₁ and Tb₄O₇ of trade.

An alloy is bought as the alloy, so its metals arrive through the LCA rather than through an
asserted composition. A steel's manganese, molybdenum and nickel are that dataset's own, as
are its chromium and iron; the study tracks the first three because its screens admit them.
Measured this way they are ore disturbed, not metal contained, which is the basis every
other intensity here is on.

`mineral` names the metal a material is bought *as*, and is what `reconcile_metal_selection`
reads to catch a metal the foreground buys and does not count. It is blank for an alloy, and
for `samarium-europium-gadolinium oxide`, which is three metals.

## `data/motor_substitution_info.csv`

`Månberger and Stenqvist - 2018 - Global metal flows in the renewable energy
transition.pdf` — A. Månberger & B. Stenqvist, *Global metal flows in the renewable
energy transition: exploring the effects of substitutes, technological mix and
development*, Energy Policy 119 (2018) 226–241.

`EV motor, induction` is derived from `EV motor, PM` rather than transcribed. The two
machines share housing, stator core, stator winding, bearings and shaft, and differ at
the rotor: permanent magnets on steel against an aluminium squirrel cage on laminated
steel. Two things change, and the file gives a factor for each:

- **Copper ×2.4253.** Table 3 (p. 230) gives 0.48105 kg Cu/kW for an induction motor
  (Dorrell et al. 2010) against 0.19835 for a permanent-magnet one (Burress et al.
  2011); 0.48105 / 0.19835 = 2.4253.
- **Nd, Pr, Dy, Tb ×0.** No permanent magnet.

Only the ratio is taken, not the level. The paper's absolute intensities are contained
metal in the product, while an LCI row is the metal disturbed in the ore so a
transcribed level set against an LCI row would report that disagreement
as part of what the market-share scenario between the two motors does. Anchoring the level
to ecoinvent and taking only the ratio is the reasoning of the conductor substitution
above.

Every other mineral is carried over untouched.

## `data/metal_densities.csv`
Densities of the two conductor metals, used with the cross sections above to turn the equal-resistance pairing into a mass ratio. Standard pure-metal values at 20 °C; the source is in the CSV.

## `data/recovery_rates.csv`

`nassar_2022_SI.pdf` — supporting information to N.T. Nassar, G.W. Lederer, J.L.
Brainard, A.J. Padilla & J.D. Lessard, *Rock-to-metal ratio: a foundational metric for
understanding mine wastes*, Environmental Science & Technology 56 (2022) 6710–6721.

A recovery rate here is the fraction of metal retained between mining output and the
final market-ready metal, i.e. the **F/E column ("smelter/refinery recovery rate") of
Table S4** (PDF page 5), which reports it per commodity as a global production-weighted
ratio of finished production to metal contained in concentrate. Twelve of the study's
metals have a row there and are transcribed as printed: Al 98 %, Co 90 %, Cu 90 %,
Ga 95 %, Ir 92 %, Li 90 %, Mo 95 %, Ni 90 %, Pt 96 %, Ag 95 %, Sn 91 %, V 78 %.

Table S4 covers 25 commodities. Germanium, graphite, manganese, niobium and the
individual rare earths are not among them, so they take the **90 % default stated in
the caption of Table S2** ("Default value of 90 % was used elsewhere"), as does the
`Rare earth elements` helper row.

Where a metal appears in both tables, Table S4's rounded ratio is what is transcribed,
not Table S2's input assumption: iridium is 92.2 % in S2 and 92 % in S4, platinum
95.5 % and 96 %. Zinc is covered by Table S4 (90 %) but has no row here, because no
zinc series enters through the mine stage; `supply_helpers` raises if one ever does.

## `data/metal_screen_policy.csv`

The policy half of the metal-selection rule (`rules/metals.smk`): the EU Critical Raw
Materials Act's own lists, plus this study's reading of which metal each listed raw
material designates. All 34 Annex II rows are transcribed; the screen admits the
Annex I subset.

`EU_2024_1252.pdf` — EU, **Regulation (EU) 2024/1252** of 11 April 2024 (the Critical
Raw Materials Act), consolidated text `02024R1252 — EN — 03.05.2024 — 000.002`:

- **Annex II Section 1** (p. 59), *List of critical raw materials* — 34 entries,
  (a)–(ah), transcribed verbatim into `raw_material`, one per row.
- **Annex I Section 1** (p. 57), *List of strategic raw materials* — 17 entries,
  (a)–(q), transcribed verbatim into `annex_i_wording`.

Annex I is a subset of Annex II, so `designation` is ordered rather than exclusive:
`strategic` implies `critical`. 18 of the 34 rows are designated strategic while Annex I has only 17 entries, because
the single Annex I entry *"rare earth elements for permanent magnets (Nd, Pr, Tb, Dy,
Gd, Sm, and Ce)"* covers two Annex II rows, `heavy rare earth elements` and `light rare
earth elements`. `scripts/metal_helpers.py:policy_screen` checks both counts, so a
transcription that has lost or gained a row cannot pass quietly.

Annex II also drops the grade qualifiers Annex I carries (`lithium` against `lithium —
battery grade`), which is why the Annex I wording is kept verbatim rather than
normalised away.

The `minerals` and `technology` columns are not in either source. They are this study's
judgement of which metal a listed raw material designates *and* which of this study's
technologies contains it — a foreground claim, so it can only be made for metals an
intensity has actually been computed or read for. Critical-only rows carry the claim
too, without admitting on it: niobium and vanadium are the only two, and both clear
the literature screen anyway, which is what makes the restriction to Annex I
free rather than merely defensible.

## `data/metal_excluded.csv`

Metals a screen admits, or the foreground buys, that the study leaves out on purpose. Not
transcribed from anything — it is a record of seven decisions, and
`reconcile_metal_selection` raises unless every such metal is named here. Silicon, boron
and titanium pass the policy screen (all on Annex I, all used in a technology in this set)
and are held out because the ore is not what constrains them; zinc, cerium, zirconium and
barium are bought by a bill of materials and pass neither screen. Reasons are in the CSV.

## `data/source/bieuville_2026_SI_2.xlsx` (the literature screen)

The other half of the selection rule. `build_literature_screen` reads two sheets of the
same workbook the non-energy demand comes from:

- `Fig 2. Annual_Demand` — demand by sector, filtered to `Modelisation type == Init`
  and `Scenario == IMAGE_SSP1-26`, column `2050`. Total is the sum over sectors;
  transition-led demand is that total minus the `Other Sector Demand` row.
- `Fig 2. MiningCapacity_Results` — filtered to `Production == Primary_Production` and
  `Modelisation type == All` (the capacity trajectory shared by every scenario, so the
  ratio varies only through demand), column `2050`.

Both sides are **annual flows in a single year (2050), worldwide**, in tonnes: nothing
is cumulated, and neither side is this study's own demand or its allocated supply. The
ratio is therefore an exposure measure, not a shortage test — see `rules/metals.smk`.

Note that this reading uses a different pathway from the non-energy demand
extraction, which takes `MESSAGE-GLOBIOM_SSP2-26`; both are recorded side by side in
`sources_info.json` (`bieuville_screen` and `bieuville_ned`). It does not change which
metals are selected: at the 5% cut the two pathways differ only in niobium, which the
policy screen admits anyway, and hafnium, which reaches no technology in this set —
`reconcile_metal_selection` nonetheless treats any metal the screen admits as a
candidate, so a hafnium that crossed the cut would raise rather than pass unnoticed.

## `data/msa_consumption.csv` and `data/msa_end_use_info.csv`

The regional other-sector consumption level (`rules/ned.smk`). Both tables are
read off the JRC/DG GROW **Material System Analysis** reports listed above — one
row per *MSA material*, not per study metal, which is what lets the `Magnetic REE`
row serve neodymium, praseodymium, dysprosium and terbium at once (split between
them by `data/msa_element_composition.csv`, below).

`MSA_2018` is titled a *Material Flow* Analysis rather than a Material System
Analysis, but only on its cover: its results chapters are headed "MSA for
Aluminium" / "MSA for Copper", and they print the same two end-use pies the three
later batches do — left-hand manufactured in the EU, right-hand used in the EU —
under the same Use-step total ("the total input to use at about 5,464 kt Al",
p. 17). It is read exactly as the others are. What it does not print is the
*representative product* table, which is why aluminium's and copper's slices carry
none.

`msa_consumption.csv` is transcribed literature and is named for its contents.
`msa_end_use_info.csv` carries the transcribed pie *and* this study's verdict on
each slice, which is a decision — hence the `_info` suffix, the same
record-plus-verdict shape as `data/lci_route_info.csv`.

There is **no machine-readable MSA distribution.** The JRC data catalogue
advertises an Excel export at `https://rmis.jrc.ec.europa.eu/msa/private/index.php`;
that URL returns HTTP 404. Everything below was read by hand.

### The four reports

| file | batch | materials taken from it |
|---|---|---|
| `MSA_2018.pdf` | Passarini, Ciacci, Nuss and Manfredi 2018, *Material Flow Analysis of Aluminium, Copper, and Iron in the EU-28*, EUR 29220 EN | Aluminium, Copper |
| `MSA_2020_batteries.pdf` | Matos et al. 2020, five battery raw materials | Cobalt, Lithium, Manganese, Natural graphite, Nickel |
| `MSA_2021_nine.pdf` | Matos et al. 2021, nine raw materials | Vanadium |
| `MSA_2023.pdf` | In Extenso et al. 2023, *Update of the 2015 Material System Analyses* | Gallium, Germanium, Indium, Niobium, Platinum, Magnetic REE |

### What was read, and from where

`eu_use_consumption` is the total printed under the chapter's **right-hand**
("finished products used in the EU") pie — the *Use step*, which is
consumption-based: it counts metal arriving inside imported finished products,
which is the whole reason this source is used rather than Eurostat apparent
consumption. `world_production` is the figure the same chapter's prose gives, so
numerator and denominator stay inside one source; `world_production_stage` records
which stage that figure is, because it differs (aluminium is smelter output,
copper mine output, nickel refinery output), and the notebook's cross-check needs
it to compare like with like.

| material | report | PDF page | figure | reference year | region | unit | EU use | world production |
|---|---|---|---|---|---|---|---|---|
| Aluminium | `MSA_2018` | 17 | Fig. 5 | 2013 | EU-28 | kt Al | 5 464 | 47 600 (smelter) |
| Copper | `MSA_2018` | 22 | Fig. 10 | 2014 | EU-28 | kt Cu | 3 000 | 18 500 (mine) |
| Cobalt | `MSA_2020_batteries` | 13 | Fig. 4 | 2016 | EU-27 | kt Co | 33 | 126 (mine) |
| Lithium | `MSA_2020_batteries` | 18 | Fig. 7 | 2016 | EU-27 | kt Li | 3.2 | 38 (refinery) |
| Manganese | `MSA_2020_batteries` | 21 | Fig. 10 | 2016 | EU-27 | kt Mn | 921 | 14 000 (ferro-Mn + ferro-silico-Mn) |
| Natural graphite | `MSA_2020_batteries` | 25 | Fig. 13 | 2016 | EU-27 | kt C | 53 | 1 100 (mine) |
| Nickel | `MSA_2020_batteries` | 28 | Fig. 16 | 2016 | EU-27 | kt Ni | 350 | 1 800 (refinery) |
| Vanadium | `MSA_2021_nine` | 51 | Fig. 31 | 2015 | EU-27 | kt V | 8.7 | 80 (refinery) |
| Gallium | `MSA_2023` | 63 | Fig. 24 | 2020 | EU-27 | t Ga | 83.7 | 304 (refinery) |
| Germanium | `MSA_2023` | 69 | Fig. 27 | 2020 | EU-27 | t Ge | 44.25 | 140 (refinery) |
| Indium | `MSA_2023` | 76 | Fig. 30 | 2020 | EU-27 | t In | 56 | 944 (processed material) |
| Niobium | `MSA_2023` | 94 | Fig. 39 | 2020 | EU-27 | t Nb | 10 370 | 65 000 (mine) |
| Platinum | `MSA_2023` | 104 | Fig. 45 | **2019** | EU-27 | t Pt | 56.3 | 185.5 (mine) |
| Magnetic REE | `MSA_2023` | 116 | Fig. 51 | 2020 | EU-27 | t mREE | 879 | 53 000 (mine) |

Five things a reader should know about that table:

- **The reference year is not common.** It spans 2013 to 2020. Aluminium's share
  is a 2013 snapshot and Europe's position has moved since;
  `notebooks/ned_projections.ipynb` prints the spread.
- **Platinum's chapter is 2019, not 2020** — its own sentence says so, while every
  other chapter in that report says 2020.
- **The 2018 batch is EU-28.** Its numerator already contains the UK, which the
  modelled country set also contains, so those two rows carry
  `reference_region = EU28` and are rescaled against an EU-28 total rather than an
  EU-27 one. Treating them as EU-27 would count the UK on both sides and overstate
  aluminium's and copper's shares by about 15%.
- **Units are per chapter, and the pie labels can lie.** Germanium's pie is
  labelled `42 740` / `44 250` while its chapter states flows are in `t Ge` and
  world production is 140 t: those labels are kilograms. The unit always comes
  from the chapter's "flows and stocks are accounted in mass of …" sentence.
  `non_energy_helpers.msa_consumption` rejects any row implying an EU share above
  50%, which is what would catch the next such mismatch.
- **Natural graphite is charged one slice of its pie.** Graphite is tracked at battery
  grade, so its refractory, foundry, friction and lubricant slices are `off_grade` and
  only `Batteries (portable/mobility/e-bikes/industrial)` (8%) is charged — not the
  neighbouring `Other batteries` (5%), which is non-lithium cells using flake as a
  conductive additive. The chapter's world figure is natural mine production, but its
  Use step counts metal inside imported finished goods and the origin of the graphite
  in an imported cell is not observable, so that slice plausibly stands for anode
  graphite of either origin rather than natural alone. Not resolvable from the
  chapter, so it is left as read.

### The end-use splits — read off images

`msa_end_use_info.csv`'s `share` column is **read off pie-chart images**, not
extracted as text: the pies are pictures in all four PDFs. They were rendered at
200–700 dpi with PyMuPDF and read visually, taking the right-hand ("used in the
EU") pie in every case. That is a transcription with its own error mode, and a
reader should know which numbers carry it. The check that they sum to 1 within
±0.02 (`non_energy_helpers.msa_end_use`) is what catches a missed or
double-counted slice; the reports print whole percents, so cobalt's sum to 1.003.

`representative_product` is the chapter's own *"List of the applications and of
the corresponding representative product"* table, printed under each pie in the
2020, 2021 and 2023 batches. `MSA_2018` prints no such table, so aluminium's and
copper's slices carry none. It is transcribed because the slice labels mislead
without it: indium's "Batteries" are **primary button cells**, the magnet REEs'
"Batteries" are **NiMH cells in portable devices**, the magnet REEs' "Magnets" are
**magnets in cars and in industrial robots**, and germanium's "Satellite solar
cells" are **space power**.

`sector` is not in any source either. The four reports each use their own
vocabulary — 80 distinct application labels across the 14 materials, most of them
one report's name for one material's use — so this column maps them onto the one
small vocabulary (`EndUseSector`) the end-use figure can colour and a reader can
hold at once. Where the mapping is not obvious it follows the representative
product: platinum's "Autocatalyst" and niobium's "Automotive (Steel)" are both
`transport`, natural graphite's "Refractories" is `industry_steel`, and the
reports' own "Other"/"Miscellaneous" slices go to `other`, which names nothing
more specific and so takes no colour.

`end_use_class` and `reason` are not in any source. They are this study's verdict
on each slice, and the rule is narrow on purpose: a slice is `energy_transition`
only where its representative product is a technology this workflow builds from
its own model, so counting it as other-sector demand would double count it. Where
MSA does not resolve a slice that far — aluminium's "Electrical engineering" is
grid conductor, motors, transformers and appliances at once — the slice stays
`other` and the reason says what it contains, which makes that material's
non-energy fraction an upper bound rather than a guess.


## `data/msa_element_composition.csv`

How one slice of an MSA material's end-use pie divides between the elements the
material comprises. Needed only where a material is not a single element, which
here is `Magnetic REE` alone.

`MSA_2023` p. 113 defines the material: "the REEs used in magnets (mREEs, which
are **Nd, Pr, Tb, Dy, Sm, Gd**)", accounted throughout as `t mREE` (p. 115).
This study tracks four of those six, so the 879 t cannot be charged to an element
until the basket is divided — and the chapter nowhere prints a per-element split.

What it does print is which elements each application uses (p. 114, and the
representative products of Table 33, pp. 116–117):

| application | elements the chapter names |
|---|---|
| Magnets | Nd, Pr (NdFeB); Tb, Dy (temperature additions); Sm, Gd (SmCo) |
| Autocatalysts | Nd, Pr |
| Glass and ceramics | Nd, Pr, Sm |
| Batteries (NiMH mischmetal) | Nd, Pr |
| Metal excl. batteries | Nd, Pr, Gd |
| Phosphors and LEDs | Tb, Dy |
| Magnetic resonance imaging | Gd |
| Other uses | Pr (polishing powders), Sm (laser dopants, radiography), Gd (nuclear) |

The `mass_share` column is **this study's verdict**, not a transcription, which
is why the table carries a `reason` per row. One rule, with one exception:

- every element the chapter names for an application takes an equal share of it,
  **except** that where Nd and Pr are both named they divide their combined share
  **3:1**, the didymium ratio the two are separated in (the same constant the
  `iron ore concentrate` route carries in `rules/lci.smk`);
- `Magnets` instead takes an **assumed** NdFeB composition — Nd 0.69, Pr 0.23,
  Dy 0.04, Tb 0.01, with 0.03 to Sm and Gd for the SmCo share of the magnet
  market. Nothing is cited for those six numbers: they are the didymium rule
  above (~92% of the REE content, split 3:1) plus a few percent of heavy
  additions for the high-temperature traction and wind grades.

`Magnets` is 70% of the pie, so that one assumed row sets about 68% of the whole
split, and it is the least-founded input in `rules/ned.smk`. Replacing it with a
sourced composition is the obvious improvement — Carrara et al. 2020
(`carrara_2020.pdf`) prints NdFeB grades, and the repo's own magnet LCI
intensities imply a ratio of their own that would be checkable against the rest
of the workflow.

Shares run over all six elements, tracked or not, so the mass charged to nobody
is visible rather than implied: of the pie, 89.6% reaches the four tracked
elements, 8.4% falls to Sm and Gd, and the 2% autocatalyst slice is
`transition_displaced`. `non_energy_helpers.msa_element_composition` checks that
every slice of the pie is split, that each slice's shares sum to 1, and that
every metal reading the material has a share in it.

This is the least-founded input in `rules/ned.smk`, which is why `msa_aggregate`
is rated `medium` where `msa` is `high`. It is also not load-bearing for the
study's conclusions: no plausible split — including charging the whole basket to
neodymium — moves any of the four metals off the cluster it sits in.

## The GDP history (`retrieve_owid_gdp`)

Retrieved, not transcribed, so it is re-derivable by re-running the workflow;
recorded here because `sources_info.json` carries the URL and column name and not
the citation.

**Eurostat, OECD, IMF and World Bank (2026)** — with minor processing by Our
World in Data. *"Gross domestic product (GDP) – World Bank – In constant
international-$"* [dataset], original data *World Development Indicators*
(`NY.GDP.MKTP.PP.KD`). OWID chart `gdp-worldbank`, column `ny_gdp_mktp_pp_kd`,
international-$ at 2021 prices, 1990–2025, updated 2026-07-27.

Summed over the modelled countries it gives the observed half of the index,
2008–2025 — 2008 is the first year all 34 report, and 2025 is the last, which is
where `build_gdp_index` splices. It is deliberately **not** the `gdp` column of
the OWID energy dataset that `rules/allocation.smk` reads: that one is the
Maddison Project Database and ends at 2022.

## `data/gdp_projection.csv`

The growth path every non-energy demand level is carried across the window on
(`build_gdp_index`).

**Table II.1.14, "Potential GDP (growth rate)"**, Statistical Annex p. 179 (PDF
p. 189) of `EC_ageing_report_2024.pdf` — European Commission (DG ECFIN) and the
Economic Policy Committee, *The 2024 Ageing Report: Economic and Budgetary
Projections for the EU Member States (2022-2070)*, European Economy Institutional
Paper 279. The `EU` row is transcribed verbatim, printed percentages stored as
printed:

| 2022 | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 | 2055 | 2060 | 2065 | 2070 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 | 1.4 | 1.0 | 1.1 | 1.5 | 1.4 | 1.3 | 1.3 | 1.2 | 1.2 | 1.1 |

These are the rate reached **in** each reported year, not an average over the
period before it (the table's first column, `Ch 22-70`, is the change between the
ends, and −0.4 is 1.1 − 1.5). `build_gdp_index` therefore interpolates between
them rather than treating them as period means, and never extrapolates past 2070.
The dip through the 2030s and the recovery after it is labour input turning
negative and then TFP convergence taking over. The splice is at 2025, so the
first rate read is 2026's, interpolated between the 2025 and 2030 entries; the
2022 entry is never reached. Spliced onto the World Bank history the path
compounds to 1.27%/yr over 2025–2050, against the report's own 1.3% headline for
2022–2070.

Two things a reader should know:

- **It is a potential-output projection**, driven by demography and productivity
  with no policy response, so it is structurally conservative.
- **It covers the EU-27 and Norway**, which is 84% of the modelled region's GDP;
  the United Kingdom (12.4%), Switzerland (2.6%) and the Western Balkans are
  outside it. Only the growth *rate* is taken — the level it is applied to is the
  region's own, summed from the World Bank series — and over 2008–2025 the covered
  countries grew at 1.14%/yr against 1.34%/yr for the uncovered ones and 1.17%/yr
  for the region as a whole. The uncovered ones growing faster makes the proxy
  conservative, by under a percent across the window.
