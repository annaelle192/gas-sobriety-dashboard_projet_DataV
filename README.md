# Has France really cut its gas consumption?

*An individual data storytelling project. Annaelle NDE MAMA, EFREI Paris, 2026 (#EFREIDataStories2026)*

- **Live app:** [https://gas-sobriety-dashboardprojetdatav.streamlit.app/]


---

## Why this question

In autumn 2022, gas suddenly became front-page news. The war in Ukraine had sent prices soaring, Europe was worried about running out over the winter, and the French government launched an energy sobriety plan asking everyone to cut energy use by 10% within two years. People were told to turn the heating down to 19 °C.

Four years later, I wanted to know whether any of it actually happened. Did we really use less gas, or did a few mild winters simply make it look that way? Did the drop last once the crisis faded from the headlines? Was it the same everywhere in France?

Opinions on this are easy to find. I wanted to look at the meters.

## What I found

**The drop is real, large and lasting.** France used about **466 TWh of gas a year on average over 2018–2021**. In 2025 it used **341 TWh**, which is **26.9% less**, well beyond the 10% target. The decline came in steps: −8% in 2022, −21% in 2023, −24% in 2024, −27% in 2025.

**It is not just the weather.** This was the question that worried me most, because the data is not temperature-corrected. The year 2014 helped me answer it. That winter was very mild, and gas use fell by 10.6% with no sobriety plan at all. The following year, it bounced straight back. Since 2023, by contrast, every year has stayed far below the pre-crisis level. A mild winter explains a dip, but not a drop that is twice as large and still holding three years later.

**Heating is only part of the story.** In volume, most of the gas saved was saved in winter, which is what you would expect. In proportion, though, the drop is even stronger outside the heating season: −33% from April to September, against −24% from October to March. Nobody heats their home in July, so that part has to come from industry and gas-fired power plants. This surprised me, and it changed how I read the whole dataset.

**Every region fell, but not at the same pace.** Provence-Alpes-Côte d'Azur shows the largest drop (−39%), followed by Hauts-de-France. Brittany shows the smallest (−9%), and its curve has an odd peak in 2022. I looked into it, and a likely explanation is the Landivisiau gas-fired power plant in Finistère, which [entered commercial service in March 2022](https://www.linfodurable.fr/finistere-mise-en-service-jeudi-de-la-centrale-au-gaz-de-landivisiau-31579). I present this as a hypothesis, not a proven cause, but it is a good reminder of what this data really measures.

**Daily habits did not change, only the level.** On a winter day, gas use still peaks around 7:00 and again around 18:00. In 2025 the curve keeps exactly the same shape, about 21% lower at every hour. People did not shift their consumption to other times of day: they simply used less.

**Gas was not swapped for electricity.** If households had replaced their gas boilers with electric heating, electricity use would have gone up. It went down too: in 2025, gas stands at index 73 and electricity at 96, where 100 is the 2018–2021 average.

## The data

| | |
|---|---|
| Main dataset | [Consommation quotidienne brute régionale](https://www.data.gouv.fr/datasets/consommation-quotidienne-brute-regionale), data.gouv.fr |
| Control dataset | [Consommation quotidienne brute](https://www.data.gouv.fr/datasets/consommation-quotidienne-brute) (national level), data.gouv.fr |
| Producers | NaTran (formerly GRTgaz), Teréga and RTE, published by Open Data Réseaux Énergies (ODRÉ) |
| Licence | Licence Ouverte / Open Licence 2.0 (Etalab) |
| Coverage | 12 regions of mainland France (Corsica excluded), 1 January 2013 to 31 August 2026 |
| Granularity | Gas every hour (MW, gross calorific value); electricity every half-hour (MW) |
| Map outlines | Simplified region boundaries from the open-source [france-geojson](https://github.com/gregoiredavid/france-geojson) project |

The raw regional file has about 2.9 million rows. I chose it because it gives both time (13 years, hour by hour) and geography (regions). It also comes with a national file, which let me cross-check it.

## How I built it

I worked in three steps, each in its own file.

**1. Getting the data and looking at it before touching it** (`etape1_donnees.ipynb`)
The notebook asks the data.gouv.fr API for the latest version of each file and downloads it. If the file is already there, it does not download it again. It then checks everything before any cleaning: columns, period covered, missing values, duplicates, status of the data, and whether the 12 regions add up to the national total.

Some "problems" turned out not to be problems at all. Half of the rows have no gas value, which looked alarming at first. In fact gas is measured every hour while the file has a row every half-hour (for electricity), so the "hh:30" rows never have a gas value. Likewise, Teréga only operates in 3 regions, so its column is empty everywhere else.

**2. Cleaning and preparing small tables** (`etape2_preparation.ipynb`)
- **Phantom hours:** when the clocks go forward at the end of March, the hour between 2:00 and 3:00 does not exist, yet the file contains rows for it. I removed these 336 rows, otherwise those days would count 24 hours of gas instead of 23.
- **Outliers:** one negative electricity value (impossible for a consumption) and one invalid status label were set to missing.
- **Incomplete days:** 30 region-days out of 59,892 have a missing hour. I flagged them rather than deleting them, so the app can exclude them from comparisons.
- **From power to energy:** values are in MW, so I converted them to GWh. Gas is summed hour by hour; electricity half-hour by half-hour, times 0.5.
- **Pre-aggregation:** about 300 MB of raw data becomes about 7 MB of tables (daily by region, hourly profiles, quality tables), so the app loads quickly.

Every operation is written to `journal_nettoyage.csv`, and the app shows this log in its data quality section.

**3. Telling the story** (`app.py`)
The Streamlit app follows the questions above, one section at a time. Each section opens with a one-sentence takeaway in bold, computed from the filters. The reader can change the energy, regions, years and the year studied, and every chart and figure updates.

| Section | Question it answers | Chart |
|---|---|---|
| At a glance | How much, compared with before the crisis? | Key figures |
| Before / after | Is the drop real and lasting? | Yearly bars with a reference line and annotations |
| Month by month | Is it only about winter? | Monthly line with the 2018–2021 range |
| Regions | Where is it strongest? | Map, ranking and one small chart per region |
| Through the day | Did habits change? | Hourly profile, winter or summer |
| Gas vs electricity | Was gas replaced? | Both energies as an index on one scale |
| Data quality | Can we trust this? | Cleaning log, data status, regional vs national gap |
| Key takeaways | So what? | Conclusions, limitations, next steps |

A few choices I made on purpose:
- **No chart with two y-axes.** Gas and electricity are compared as an index (100 = 2018–2021), so they share one scale.
- **Small multiples for the regions,** rather than 12 lines tangled on one chart.
- **A colour-blind-safe palette,** a text description under every chart, and units on every axis.

## Can the data be trusted?

Mostly yes, and I tried to show why rather than just say it.

- The 12 regions add up to the national total: the median daily gap is **0.00% over 4,991 days**.
- On full hours, fewer than 0.01% of gas values are missing.
- **2013 is the exception.** In early 2013, the regions add up to about 15% less than the national total, and the split between regions looks wrong (Île-de-France unusually low, Occitanie unusually high). I hide that year by default and keep it out of the reference period.
- The network operator corrected ("redressé") its 2022 gas data, and recent electricity values are still "consolidated", meaning they can still be revised.

## Limitations

I would rather be clear about what this project cannot say.

- **Weather.** The data is raw, not temperature-corrected. The comparison with 2014 is a strong clue, but it is not a proper weather correction.
- **Mixed causes.** The gas transmission network supplies homes, businesses, large factories and power plants. This data cannot tell how much of the drop comes from households saving energy, from factories producing less, or from power plants running less.
- **Correlation, not causation.** The drop starts with the 2022 crisis, but this data alone cannot prove that the sobriety plan caused it. High prices certainly played a part too.
- **2026 is incomplete.** It stops at the end of August, so the app always compares it with the same months of 2018–2021.
- **Privacy.** The data is aggregated by region, and nothing in it relates to individuals.

## What I would do next

- Correct for the weather using heating degree days, to isolate the sobriety effect.
- Use distribution-network data to separate households from industry and power plants.
- Watch winter 2026–2027, to see whether the drop holds as prices come back down.

## Running it yourself

```bash
pip install -r requirements.txt
```

1. Open `etape1_donnees.ipynb` in Jupyter and run all cells. It downloads the raw data (about 300 MB, not included in this repository) and checks it.
2. Open `etape2_preparation.ipynb` and run all cells. It creates the five tables used by the app.
3. Start the app: `streamlit run app.py`

The five prepared tables are already included here, so step 3 works on its own. There is no random sampling anywhere: the whole dataset is used, so the results are the same on every run.

## Files

| File | What it is |
|---|---|
| `app.py` | The Streamlit app |
| `etape1_donnees.ipynb` | Download (with caching) and first quality checks |
| `etape2_preparation.ipynb` | Cleaning and pre-aggregation |
| `conso_jour_region.csv` | Gas and electricity per day and region (GWh) |
| `profil_horaire.csv` | Average power per hour, region, month and year (MW) |
| `qualite_statuts.csv` | Share of values by status and year |
| `qualite_validation.csv` | Daily gap between the sum of the regions and the national total (%) |
| `journal_nettoyage.csv` | Every cleaning step and the number of rows it affected |
| `regions.geojson` | Region outlines for the map |
| `requirements.txt` | Python libraries, with pinned versions |

**Main table (`conso_jour_region.csv`):** `jour` is the date (local time). `annee`, `mois` and `jour_semaine` give the year, month and weekday (0 = Monday). `hiver` is the heating winter, October to March (e.g. "2022-2023"). `code_region` and `region` give the INSEE code and name. `gaz_gwh` and `elec_gwh` are the daily consumption in GWh. `heures_gaz` and `heures_attendues` count the hours of gas filled in and expected; `demi_heures_elec` and `demi_heures_attendues` do the same for electricity. `complet` is true when nothing is missing.

## Licences

- **Data:** Licence Ouverte / Open Licence 2.0 (Etalab). Source: NaTran, Teréga, RTE via ODRÉ, published on data.gouv.fr.
- **Code:** MIT licence. Feel free to reuse it, with credit.
