import copy
import datetime 
from datetime import datetime
import re 
import numpy as np 
import pandas as pd 
from PIL import Image 
import streamlit as st 
from streamlit import markdown as md 
from streamlit import caching
import gsheet

LOCAL = True

def is_unique(s):
    a = s.to_numpy() # s.values (pandas<0.24)
    return (a[0] == a).all()


def st_config():
    """Configure Streamlit view option and read in credential file if needed check if user and password are correct"""
    st.set_page_config(layout="wide")
    pw = st.sidebar.text_input("Enter password:")
    if pw == "":#st.secrets["PASSWORD"]:
        if LOCAL:
            return ""
        else:
            return st.secrets["GSHEETS_KEY"]
    else:
        return None

@st.cache
def read_data(creds):
    """Read court tracking data in and drop duplicate case numbers"""
#    try:
    df = gsheet.read_data(gsheet.open_sheet(gsheet.init_sheets(creds),"01_Community_lawyer_test_out_final","Frontend"))
    #    df.drop_duplicates("Case Number",inplace=True) #Do we want to drop duplicates???
    return df
#    except Exception as e:
#        return None


#def date_options(min_date,max_date,key):
#    cols = st.beta_columns(2)
#    key1 = key + "a"
#    key2 = key + "b"
#    start_date = cols[0].date_input("Start Date",min_value=min_date,max_value=max_date,value=min_date,key=key1)#,format="MM/DD/YY")
#    end_date = cols[1].date_input("End Date",min_value=min_date,max_value=max_date,value=datetime.today().date(),key=key2)#,format="MM/DD/YY")
#    return start_date,end_date

#UI start date end date/ eviction motion or both drop duplicates?:
def date_options(df):
    min_date = df.court_date.min().date()
    max_date = df.court_date.max().date()
    start_date = st.sidebar.date_input("Start Date",min_value=min_date,max_value=max_date,value=min_date)#,format="MM/DD/YY")
    end_date = st.sidebar.date_input("End Date",min_value=min_date,max_value=max_date,value=max_date)#,format="MM/DD/YY")
    df = filter_dates(df,start_date,end_date)
    st.sidebar.markdown(f"### {start_date} to {end_date} cases tracked: "+str(len(df)))
    return df 


def filter_dates(df,start_date,end_date):
    return df.loc[(df["court_date"].apply(lambda x: x.date())>=start_date) & (df["court_date"].apply(lambda x: x.date())<=end_date)]  
  

def motion_options(df):
    motion = st.sidebar.radio("Motion Hearing, Eviction Trial, Both",["Both","Motion Hearing","Eviction Trial"])
    return filter_motion(df,motion)
    

def filter_motion(df,motion):
    if motion != "Both":
        df = df.loc[df["motion_hearing"].eq(motion)]
        st.sidebar.markdown(f"### {motion}s tracked: "+str(len(df)))
    else:
        st.sidebar.markdown(f"### Eviction Trials and Motion Hearings tracked: "+str(len(df)))
        pass 
    return df


def agg_cases(df,col,i):
    df_r = df.groupby([col,"Case Number"]).count().iloc[:,i]
    df_r.name = "count"
    df_r = pd.DataFrame(df_r)
    df_a = pd.DataFrame(df_r.to_records())
    df_r = df_r.groupby(level=0).sum()
    df_r["cases"] = df_a.groupby(col)["Case Number"].agg(lambda x: ','.join(x))
    return df_r


def agg_checklist(df_r):
    df_r["result"]=df_r.index
    df_b = pd.concat([pd.Series(row['count'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").sum()
    df_a = pd.concat([pd.Series(row['cases'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").agg(lambda x: ", ".join(x))
    df_r = df_b.merge(df_a,right_index=True,left_index=True)
    return df_r 

def clean_df(df):
    df = df.astype(str)#maybe not the best way to fix this... as we cant do sums now bug with int vars showing up two things on the bargraph
    df["court_date"] = pd.to_datetime(df["court_date"]) 
    return df

#Show more text on full screen dataframe 
def render_page(df):
    """Function to render all of the pages elements except the api key login"""
    #Clean Data
    df = clean_df(df)
    
    #All Data Stats
    st.header("Court Tracking Data")
    cols = st.beta_columns(4)
    
    #Collapsible All Data
    with st.beta_expander("All Data"):
        st.dataframe(df)
        st.markdown("### Total Cases Tracked: "+str(len(df)))


    #Render and Evaluate UI options
    df = date_options(df) 
    df = motion_options(df)

    #Render Each column as a data frame and a Bar Graph
    check_list = ["Technical Problems?","Plaintiff Representation","Tenant Representation","Fee Types","NTV Communicated By","Breach of Lease"]
    for i,col in enumerate(df.columns):
        try: #this fails on Case Number probably should fix it but ehh
            df_r = agg_cases(df,col,i)
            if col in check_list: 
                df_r = agg_checklist(df_r)
            df_r.columns = ["Count","Cases"]
            
            try: #Fails where no na's
                count_na = str(df_r.loc[""]["Count"])
                df_r = df_r.drop("") 
            except:
                count_na = 0
            
            if not df_r.empty:
                col1, col2 = st.beta_columns(2)
                col1.header(col)
                #What sizes do we want here?
                col1.dataframe(df_r)
                col2.header(col)
                col2.bar_chart(df_r)
            else:
                md(f"## {col} is empty")
            md(f"### Total Unanswered: {count_na}") 
        except Exception as e: 
            pass



if __name__ == "__main__":
    creds = st_config()
    if creds is not None:
         if LOCAL:
             df = pd.read_csv("../data/01_Community_lawyer_test_out_final - Backend.csv")
             df_e = pd.read_csv("../data/Court_scraper_evictions_archive - evictions_archive.csv")
             df_s = pd.read_csv("../data/Court_scraper_eviction_scheduler - eviction_scheduler.csv")
             df_c = pd.read_csv("../data/Court_contact_data_PIR.csv")
         else:
             df = copy.deepcopy(read_data(creds)) #Displays invalid API Key error on web page
         render_page(df)
    else:
        caching.clear_cache()
        st.text(f"Invalid password.")
