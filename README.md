# Olympics Heat Stress Figures 
Reproduces figures from Raeber et al., *"Increasing risk of heat stress at the Summer Olympics"*
(Nature Cities). Figure 2 is reproduced by a separate script. 

## Inputs & Data
The `olympics-heat-stress` Jupyter notebook requires files provided in the `data` folder. This includes information about 
past Olympics, cities, and sports, as well as files containing the heat stress risk and event suspension probabilities 
calculated using methodology from Tartarini et al. 2025. The code adapted from Tartarini et al. 2025's pythermalcomfort 
is included in `sport_heat_stress`, but the heat risk analysis was conducted on NSF NCAR's Casper cluster and scripts 
are not included. 

Figure 1 also requires external data from the CHC-CMIP6 dataset by Williams et al. 2024, omitted from this repository 
for size. You can download the historical daily maximum temperature (Tmax) and corresponding relative humidity (RHx) 
at https://data.chc.ucsb.edu/products/CHC_CMIP6/. Details on the xarray dataset object are included in the notebook. 

## Reproducibility
Generated with proplot 0.9.7, numpy 1.26.4, pandas 1.5.3, xarray 2023.6.0 on Python 3.9.17.  
