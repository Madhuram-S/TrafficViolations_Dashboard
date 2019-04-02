#import all dependencies
import os

import pandas as pd
import numpy as np

import sqlalchemy
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy import func, distinct # library to use aggregate functions
from sqlalchemy.sql import operators

# ############## Not required when Integrated with Flask
# # Declare global variables
# dbPath = "trafficViolations/static/db"
# dbName = "trafficViolations.sqlite"

# # create the connection to SQLite db
# eng = create_engine(f"sqlite:///{dbPath}/{dbName}")

# # reflect an existing database into a new model
# Base  = automap_base()

# #prepare and reflect all tables wih data
# Base.prepare(eng, reflect = True)

# print(Base.classes.keys())

# V = Base.classes['traffic_violations']

# # create session
# session = Session(bind = eng)


# ### HELPER FUNCTION FOR DATA Extraction USING SQL QUERIES
# 

# extract unique years
def getYears(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.Year)).all(), columns = ['Year'])
    res['Year'] = res['Year'].astype(str)
    return res

#getYears()

# extract uniq Months
def getMonths(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.Month)).all(), columns = ['Month'])
    res['Month'] = res['Month'].astype(str)
    return res

#getMonths()

# extract uniq Qtr
def getQtrs(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.Qtr)).all(), columns = ['Qtr'])
    res['Qtr'] = res['Qtr'].astype(str)
    return res

#getQtrs()

# extract uniq SubAgency and Police District
def getPoliceDist(db, V):
    res = pd.DataFrame(db.session.query(V.SubAgency,V.PoliceDistrictID).distinct().all(), columns = ['SubAgency','PoliceDistrictID'])
    res['PoliceDistrictID'] = res['PoliceDistrictID'].astype(str)
    return res

# getPoliceDist()

# extract uniq ViolaitonCategory
def getVioCat(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.ViolationCategory)).all(), columns = ['ViolationCategory'])
    return res

# getVioCat()

# extract uniq ViolationType
def getVioType(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.ViolationType)).all(), columns = ['ViolationType'])
    return res

# getVioType()

# extract uniq Vehicle Grp
def getVehGrp(db, V):
    res = pd.DataFrame(db.session.query(distinct(V.VehicleGroup)).all(), columns = ['VehicleGroup'])
    return res

# getVehGrp()

def summarize_YR_QTR(db, V):
    res = pd.DataFrame(db.session.query(V.Year, V.Qtr, func.sum(V.ViolationCount)).\
    	group_by(V.Qtr).group_by(V.Year).all(), columns = ['Year', 'Qtr','Total_ViolationCount'])
    return res

# summarize_YR_QTR()

def violation_YOY_Change(db, V):
	""" FUNCTION: violation_YOY_Change """
	""" desc : extract violation count by year and qtr, calculates Year-on-year change"""
	""" return DataFrame with Year, Qtr, Total Violations, YOY % """

	df = summarize_YR_QTR(db, V)
	df_yoy = pd.pivot_table(df, values = "Total_ViolationCount", index = ['Year'], columns = ["Qtr"], aggfunc = np.sum)
	#caclculate year on year change
	df_yoy = df_yoy.pct_change()
	# drop na
	df_yoy = df_yoy.dropna(how = "any")

	# reshape to normal dataframe strcuture
	df_yoy = pd.DataFrame(df_yoy.unstack())
	df_yoy.rename(columns = {0: 'YOY_Change_PCT'}, inplace = True)
	df_yoy.reset_index(inplace = True)

    #merge total violations and yoy df for final df
	df_final = pd.merge(df, df_yoy, on = ['Year','Qtr'])

	return df_final
    
    
#violation_YOY_Change() 

def dist_Contrib_YOY(db, V):
	""" FUNCTION: dist_Contrib_YOY """
	""" desc : extract violation count by district year and qtr, calculates each dist contribuion % """
	""" return DataFrame with Year, Qtr, Police District, Total Violations, Contribution % """

	res = pd.DataFrame(db.session.query(V.SubAgency, V.Year, V.Qtr, func.sum(V.ViolationCount)).
    			group_by(V.SubAgency).group_by(V.Qtr).group_by(V.Year).all(),
    			columns = ['SubAgency','Year', 'Qtr','Total_ViolationCount'])
    
    #   reshape result to calculate diff between Qtrs
	df_diff = pd.pivot_table(res, values = "Total_ViolationCount", index = ['SubAgency','Qtr'], columns = ['Year'])
    #calculate difference
	df_diff = df_diff.diff(axis = 1)
    
    # unstack to remove multilevel index
	d = df_diff.unstack().unstack().reset_index()
    
    #drop NAN and reset index
	d.dropna(how = "any", inplace = True)
	d.reset_index()
    
    # extract the data for total values
	df_tot = summarize_YR_QTR(db, V)
    
    # iterate to calculat the Contribution %
	df_result = []
	for index, row in d.iterrows():
		pct = (row[0]/(df_tot[(df_tot['Year'] == row.Year-1) & (df_tot.Qtr == row.Qtr)]['Total_ViolationCount'])).iloc[0]    
		df_result.append({
			'Year': row.Year,
			'Qtr':row.Qtr,
			'SubAgency':row.SubAgency,
			'Contrib_pct':pct
		})
        
        
    # merge data for violations by district/qtr/year with contribution pct
	df_final = pd.merge(res, pd.DataFrame(df_result), on = ['SubAgency','Qtr','Year'])
    
	return df_final
    
#dist_Contrib_YOY()

# function to extract Violation  by district
# parameters Year (All, specific Year), Category (All & specific category) and District (All and specific)
def filterData_main(db, V, yr = 0, cat = "all", dist = 0):
    
    _filter = [1==1, V.Qtr.in_([1,2,3,4])]
    
    if(yr != 0):
        _filter.append(V.Year.in_([yr]))
    
    if(cat != "all"):
        _filter.append(V.ViolationCategory.in_([cat]))
    
    if(dist != 0):
        _filter.append(V.PoliceDistrictID.in_([dist]))
    
    
    #list of items to select
    selList = [V.Year,V.Qtr,V.Month,V.SubAgency,V.PoliceDistrictID,V.ViolationType,V.ViolationCategory,
               V.VehicleGroup,V.PersonalInjury,V.PropertyDamage,V.Fatal,V.ContributedToAccident,V.ViolationCount]
    
    res = db.session.query(*selList).filter(*_filter).all()
                       
    df = pd.DataFrame(res, columns = ["Year","Qtr","Month","SubAgency","PoliceDistrictID","ViolationType",
                                      "ViolationCategory","VehicleGroup","PersonalInjury","PropertyDamage","Fatal",
                                      "ContributedToAccident","ViolationCount"])
    
    return df


def getViolation_ByDist(db, V,yr, cat, dist):
    """ FUNCTION: getViolation_ByDist """
    """ desc : extract violation count by district and other filters as given by user (Year, Category and District) % """
    """ return DataFrame with SubAgency, Police District, Total Violations """
    
    df_all = filterData_main(db, V,yr, cat, dist)
    
    df_all = df_all[['SubAgency','PoliceDistrictID','ViolationCount']].\
                groupby(['SubAgency','PoliceDistrictID']).agg(np.sum)
    
    df_all.reset_index(inplace = True)
    
    return df_all

#getViolation_ByDist(0,"all",0)

def getViolation_ByCat(db, V, yr, cat, dist):
    """ FUNCTION: getViolation_ByCat """
    """ desc : extract violation count by Category and other filters as given by user (Year, Category and District) % """
    """ return DataFrame with ViolationCategory, Total Violations """
    
    df_all = filterData_main(db, V,yr, cat, dist)
    
    df_all = df_all[['ViolationCategory','ViolationCount']].\
                groupby(['ViolationCategory']).agg(np.sum)
    
    df_all.reset_index(inplace = True)
    
    return df_all

# getViolation_ByCat(0,"all",0)

def getViolation_ByType(db, V, yr, cat, dist):
    """ FUNCTION: getViolation_ByType """
    """ desc : extract violation count by Violation Type and other filters as given by user (Year, Category and District) % """
    """ return DataFrame with ViolationType, Total Violations """
    
    df_all = filterData_main(db, V, yr, cat, dist)
    
    df_all = df_all[['ViolationType','ViolationCount']].\
                groupby(['ViolationType']).agg(np.sum)
    
    df_all.reset_index(inplace = True)
    
    return df_all

# getViolation_ByType(0,"all",0)
