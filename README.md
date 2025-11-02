# TRANS
Tool for Research and Analysis of Nano Spectroscopy

The aim of the project is to provide a dynamic worflow for analyzing STS measurements taken with Nanosurf brand Scanning Tunneling
Microscopes. The code is made to analyze larger ammounts of data, especially but not restricted to STS maps. The methods can be applied
to other microscopes,contingent only on the data formatting. Soon the code will be updated to accept measurements from Omicron brand 
tunneling microscopes as well as Atomic Force Microscopy spectra taken on Park AFM brand microscopes.

The code is implemented in Python 3.13.4 and was developed on MacOS, but should run well on any python3 installation. 

DATA INPUT AND OUTPUT 

Input: A series of .NID microscopy image files, which are processed using Nanosurf's proprietary library to convert the data to a 
Pandas dataframe consisting of one column of V (electric potential/bias voltage) values in Volts and an arbitrary number of subsequent 
columns containing the I (electrical current/tunneling spectrum) values in Ampères. Any dataset so formatted should work, bypassing the
need for Nanosurf's library NSFopen.

Output: The user can obtain results from any point in the normal workflow of analysis of Tunneling spectroscopy measurements we are all
familiar with. You can obtain besides the raw I-V curve data its derivatives (as CSV files), spatial reconstructions of the scanning 
tunneling image from the spectra (which essentially means choosing which bias voltage to analyze the sample at AFTER THE FACT, for any V
value as TIFF images), statistically robust spectral analysis by discretizing the map's grid and grouping each section's spectra with 
good spatial accuracy,as well as any form of creative data visualization, which allows for a top-down view of unwieldly large datasets.
