import copy
import datetime 
from datetime import datetime, timedelta
import math
import re
 
import numpy as np 
import pandas as pd 
from PIL import Image 
import plotly.express as px 
from plotly.subplots import make_subplots
import streamlit as st 
from streamlit import markdown as md 
from streamlit import caching

import gsheet

LOCAL = False

def is_unique(s):
    a = s.to_numpy() # s.values (pandas<0.24)
    return (a[0] == a).all()


def st_config():
    """Configure Streamlit view option and read in credential file if needed check if user and password are correct"""
    st.set_page_config(layout="wide")
    pw = st.sidebar.text_input("Enter password:")
    if pw == st.secrets["PASSWORD"]:
        return st.secrets["GSHEETS_KEY"]
    else:
        return None

@st.cache
def read_data(creds,ws,gs):
    """Read court tracking data in and drop duplicate case numb
ers"""
#    try:
    df = gsheet.read_data(gsheet.open_sheet(gsheet.init_sheets(creds),ws,gs))
    #    df.drop_duplicates("Case Number",inplace=True) #Do we want to drop duplicates???
    return df
#    except Exception as e:
#        st.write(e)
#        return None


def date_options(min_date,max_date,key):
    quick_date_input = st.selectbox("Date Input",["Custom Date Range","Previous Week","Previous 2 Weeks","Previous Month (4 weeks)"],0,key=key)
    if quick_date_input == "Previous Week":
        start_date = (
            datetime.today() - timedelta(weeks=1)
        ).date()
        end_date = datetime.today().date()
    if quick_date_input == "Previous 2 Weeks":
        start_date = (
            datetime.today() - timedelta(weeks=2)
        ).date()
        end_date = datetime.today().date()
    if quick_date_input == "Previous Month (4 weeks)":
        start_date = (
            datetime.today() - timedelta(weeks=4)
        ).date()
        end_date = datetime.today().date()
    if quick_date_input == "Custom Date Range":
        key1 = key + "a"
        key2 = key + "b"
        cols = st.beta_columns(2)
        start_date = cols[0].date_input("Start Date",min_value=min_date,max_value=max_date,value=min_date,key=key1)#,format="MM/DD/YY")
        end_date = cols[1].date_input("End Date",min_value=min_date,max_value=max_date,value=datetime.today().date(),key=key2)#,format="MM/DD/YY")

    return start_date,end_date

def filter_dates(df,start_date,end_date,col):
    df = df.loc[
        (df[col].apply(lambda x: x)>=start_date) & 
        (df[col].apply(lambda x: x)<=end_date)
    ]
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


def convert(x):
    try:
        return x.date()
    except:
        return None

def convert_date(df,col):
    """Helper function to convert a col to a date"""
    df[col] = pd.to_datetime(df[col]).apply(lambda x: convert(
x))
    #convert NaTs to None
    df[col] = (
        df[col]
        .astype(object)
        .where(df[col].notnull(), None)
    )
    return df

def clean_df(df):
    """clean data and convert types for display"""
    df.fillna("",inplace=True)
    df = df.astype(str)
    return df

def court_tracking_data(df,df_s,df_e):
    with st.beta_expander("Court Tracking Data"):
        #set up UI date filter element 
        try:
            min_date = df["court_date"].min()-timedelta(days=7)
        except: #happens when nulls are in court_date column
            min_date = df["court_date"].iloc[0]
        max_date = datetime.today().date()+timedelta(days=90)
        start_date,end_date = date_options(
            min_date,max_date,"1"
        ) 
        
        #Filter data by date
        df_f = filter_dates(
            df,
            start_date,
            end_date,
            "court_date"
        )
        df_ef = filter_dates(
            df_e,
            start_date,
            end_date,
            "date_filed"
        )
        #get rid of motion hearings now that we have there stats finished
        df_fe = df_f[df_f['motion_hearing']!='Motion Hearing']
                  
        #Court tracker volunteer stats
        cols = st.beta_columns(2)
        if cols[0].checkbox("Volunteer Data (click to expand)"):
            cols1 = st.beta_columns(2)
            cols1[0].markdown("## Volunteer Tracker Data")
            cols1[1].markdown("## ")
            cols1[0].markdown(f"### :eyes: Number of trackers:\
                {len(df_f['Tracker Name'].unique())}")
            cols1[0].write(
                df_f
                .groupby('Tracker Name')['Case Number']
                .nunique()
                .sort_values(ascending=False)
            )
        if cols[1].checkbox("Motion Hearing Data (click to expand)"):
            motion_hearings(df_f)
        #judge data 
        if cols[0].checkbox("Judge Tracked Data (click to expand)"):
            judge_data(df_fe,df_ef)
        #Technical problems
        if cols[1].checkbox("Technical Difficulties (click to expand)"):
            tech_probs(df_fe)
        #pie chart data
        if cols[0].checkbox("Pie charts (click to expand)"):
            pie_chart_build(df_fe)
        #all qualitative data
        if cols[1].checkbox("All Qualitative Data (click to expand)"):
            render_all_qual_data(df_fe)


def pie_chart_build(df_fe):
    cols = st.beta_columns(2)        
    cols[0].markdown("## Pie Charts for Selected Responses")
    cols[1].markdown("## ")
    #pie chart columns 
    pie_chart_cols = [
    	"Final Case Status",
        "RRT Referal",
        "Appeals Discussed",
#       "NPE Discussion",
        "NTV Discussed",
        "Tenant Representation",
        "Plaintiff Representation",
        "Poor Conditions Discussed?",
        "Tenant Type",
        "Eviction Reason",
        "Owner or Property Manager Race",
        "Tenant Race",
        "Property Type", #also include property subsidy?
        "Defendant Language",
        "Interpretation Provided",
        "Digital Divide Issues",
    ]
    pie_chart_qcols = [
        ["Other Final Status","Dismissal Reason","Other Dismissal Reason","Abated Reason","Other Abated Reason"],
        ["RRT Details"],
        ["Appeals Details"],
#        ["NPE Date","NPE Comments"],
        ["NTV Details","NTV Date","NTV Communicated By","Other NTV Communication"],
        ["Tenants Name","Tenant Attorney","Other Tenant Representation"],
        ["Owner or Property Manager Name","Attorney Details","Nationwide Details","Other Plaintiff Representative Details","Plaintiff Details"],
        ["Poor Condition Details"],
        ["Other Tenancy Details"],
        ["Breach of Lease","Other Breach of Lease"],
        None,
        ["Other Tenant Race"],
        ["Property Name","Property Address","Property Managament","Property Details","Unit Size"],
        None,
        ["Langauage Access Comments"],
        ["Digital Divide Details"]
    ]
    for col,qcols in zip(pie_chart_cols,pie_chart_qcols):
        pie_chart(
            df_fe,
            col,
            cols,#display columns
            qcols
        ) 

def motion_hearings(df_f):
    cols = st.beta_columns(2)
    cols[0].markdown("## Motion Hearing Stats/Qualitative Data")
    cols[1].markdown("## ")
    df = df_f[df_f['motion_hearing']=='Motion Hearing']
    cols[0].markdown(f"### Total number of motion hearings: {df['Case Number'].nunique()}")
    qual_cols = ["Plaintiff Details","Defendant Details","RRT Referal","RRT Details","Misc Details"]
    render_qual_pie(df,cols,qual_cols) 


def judge_data(df_f,df_ef):
    display_cols = st.beta_columns(2) 
    display_cols[0].markdown("## Tacked and Filed Case Counts")
    display_cols[1].markdown("## ")
    #cases tracked by jp and cases filed 
    df_f["jp"] = df_f["Case Number"].str[1:2]
    df_fjp = pd.DataFrame(df_f
        .groupby('jp')['Case Number']
        .nunique()
    #    .sort_values(ascending=False)
    )
    df_ef_jp = pd.DataFrame(df_ef
        .groupby('precinct')['case_number']
        .nunique()
    #    .sort_values(ascending=False)
    )
    df = pd.DataFrame()
    for i in range(1,11):
        if i % 2 == 1 :
            idx = str(int(math.ceil(i/2)))
            df.at[i,"case_type"] = f"JP{idx} Cases Tracked" 
            df.at[i,"Case Count"] = df_fjp.loc[idx,"Case Number"]
        else:
            idx = str(int(i/2))
            df.at[i,"case_type"] = f"JP{idx} Cases Filed " 
            df.at[i,"Case Count"] = df_ef_jp.loc[idx,"case_number"]
       
    fig = px.bar(df, x='case_type', y='Case Count')
    display_cols[0].markdown("### Cases tracked and Filed by JP")
    display_cols[0].plotly_chart(fig,use_container_width=True) 
    display_cols[0].write(df)
    #cases tracked by judge
    df_fj = (df_f
        .groupby('Judge Name')['Case Number']
        .nunique()
        .sort_values(ascending=False))
    fig = px.bar(df_fj,x=df_fj.index,y='Case Number')
    display_cols[1].markdown("### Cases tracked by judge")
    display_cols[1].plotly_chart(fig,use_container_width=True) 
    display_cols[1].write(df_fj) 

def tech_probs(df_f):
    display_col = st.beta_columns(2)
    display_col[0].markdown("## Court Technical Difficulties")
    display_col[1].markdown("## ")
    #technical problems vs cases we watched by jp (technical problems) filter by date (note improvement)
    #only  care about cases with tech probs  
    df_f["jp"] = df_f["Case Number"].str[:2]
    df = df_f.loc[
        (df_f["Technical Problems?"]!="No technical issues") &
        (df_f["Technical Problems?"]!="")
    ]
    df_t = (df
        .groupby('jp')['Case Number']
        .nunique()
    )    
    fig = px.bar(df_t,x=df_t.index,y='Case Number')
    display_col[0].markdown("### Court Tech problems by JP")
    display_col[0].plotly_chart(fig,use_container_width=True) 
    #Percentage of cases with problem table by jp
    df_tot = (df_f
        .groupby('jp')['Case Number']
        .nunique()
    )    
    df_tot = df_t.to_frame().merge(df_tot.to_frame(),right_index=True,left_index=True)
    df_tot.columns = ["Cases With Tech Probs","Total Tracked Cases"]
    df_tot["Percentage"] = round(df_tot["Cases With Tech Probs"]/df_tot["Total Tracked Cases"],2)*100
    display_col[0].write(df_tot)
    #technical narrative box with all qualitative data
    display = [
        "Judge Name",
#        "Technical Problems?",
        "Other technical problems"
    ] 
    df = df_f[display]
    df = df.groupby("Judge Name").agg(lambda x: ' / '.join(x))
#    df["Technical Problems?"] = df["Technical Problems?"].apply(
#        lambda x: re.sub(',+', ' ',x)
#    )
    df["Other technical problems"] = df["Other technical problems"].apply(
        lambda x: re.sub('( / )+', ' / ',x)
    )
    display_col[1].markdown(f"### Qualitative Data")
    for idx,row in df.iterrows():
        text = ""
        for i,col in enumerate(df.columns):
            if row[col] != "":
                text += row[col] + ", "
        display_col[1].markdown(f"**{idx}** {text}")
   

def judge_data_filings(df_ef):
    display_col = st.beta_columns(2)
    display_col[0].markdown("## Filings Data")
    display_col[1].markdown("## ")
    #cases filed by judge
    df_ef['precinct'] = 'JP'+df_ef['precinct']
    df_efjp = (df_ef
        .groupby('precinct')['case_number']
        .nunique()
#        .sort_values(ascending=False)
    )
    fig = px.bar(df_efjp,x=df_efjp.index,y='case_number')
    display_col[0].markdown("### Cases filed by judge")
    display_col[0].plotly_chart(fig,use_container_width=True) 
    

def pie_chart(df,col,display,qualitative_data_cols=None):
    display[0].markdown(f"### {col} Total Unanswered: {df[df[col]=='']['Case Number'].nunique()+df[df[col]=='Unknown']['Case Number'].nunique()}/{df['Case Number'].nunique()}")
    df = df[df[col]!='']
    df_pie = df.groupby(col).count()["Case Number"]
    df_pie = pd.DataFrame(df_pie)
    fig = px.pie(
        df_pie, 
        values="Case Number", 
        names=df_pie.index, 
    )
    display[0].plotly_chart(fig)
    #render qualitative data if passed
    if qualitative_data_cols:
        qdata_cols_final = []
        for qcol in qualitative_data_cols:
            if display[0].checkbox(f"See {qcol}"):
                qdata_cols_final.append(qcol) 
        render_qual_pie(df,display,qdata_cols_final) 
    else:
        display[0].write("No qualitative data to display")


def render_qual_pie(df,display,qual_cols):
    df.reset_index(inplace=True)
    #include defendant and case nunber
    qual_cols.append('Case Details')
    qual_cols.append('Case Number')
    df = df[qual_cols]
    df.replace("Unknown","",inplace=True)
    for col in df.columns:
        if not((col == "Case Details") or (col == "Case Number")):
            display[1].markdown(f"### {col}")
            for i,entry in enumerate(df[col]):
                if entry != "":
                    display[1].markdown(f"**{df.at[i,'Case Details']}/{df.at[i,'Case Number']}:** {entry}")


def render_all_qual_data(df):
    display = st.beta_columns(2)
    display[0].markdown("## All Qualitative Data")
    display[1].markdown("## ")
    cols = [
        "Late Reason",
        "Other technical problems",
        "Other Final Status",
        "Dismissal Reason",	
        "Other Dismissal Reason",
        "Abated Reason",
        "Other Abated Reason",
        "Postponed Date",
        "Fee Details",
        "Attorney Details",	
        "Nationwide Details",	
        "Other Plaintiff Representative Details",
        "Plaintiff Details",
        "Defendant Details",	
        "Langauage Access Comments",
        "Disability Accomodations Details",
        "Digital Divide Details",
        "Property Name",
        "Property Address",
        "Property Managament",
        "Property Details",	
        "COVID Details",
        "Poor Condition Details",
        "Details About Documents and Evidence Shared with Tenant",
        "Other Tenancy Details",
        "Late Fees/ Other Arrears",
        "Tenant Dispute Amount",
        "NTV Details",
        "Other NTV Communication",
        "CDC Details",	
        "NPE Comments",	
        "Appeals Details",
        "RRT Details",	
        "Misc Details",
        "Other Breach of Lease",
        "Plaintiff Attorney",	
        "Nationwide Name",	
        "Other Plaintiff Representation",
        "Tenant Attorney",
        "Other Tenant Representation",
    ]
    df.reset_index(inplace=True)
    #include defendant and case nunber
    cols.append('Case Details')
    cols.append('Case Number')
    df = df[cols]
    df.replace("Unknown","",inplace=True)
    for col in cols:
        if not((col == "Case Details") or (col == "Case Number")):
            if display[0].checkbox(f"Qualitative data for {col} (click to expand)"):
                display[1].markdown(f"### {col}")
                for i,entry in enumerate(df[col]):
                    if entry != "":
                        display[1].markdown(f"**{df.at[i,'Case Details']}/{df.at[i,'Case Number']}:** {entry}")
     
    
def setting_data(df_s):
    #(settings now to ~90 days out)
    container = st.beta_container()
    cols_container = container.beta_columns(2)
    cols = st.beta_columns(2)
    days = cols[0].slider(
        "Days out?",
        0,
        90,
        90
    )
    df_sf = filter_dates(
        df_s,
        datetime.today().date(),
        (datetime.today()+timedelta(days=days)).date(),
        "setting_date"
    ) 
    cols_container[0].markdown(f"### :calendar: Number of Settings \
        today-{days} days out: {len(df_sf)}")
    df_sf.index = df_sf["case_number"]
    cols[0].write(
        df_sf[["setting_date","setting_time"]]
    )


def judgement_data(dfj):
    display = st.beta_columns(2)
    display[0].markdown("## Case Outcomes")
    display[1].markdown("## ")
    #possesion and monetary judgement by jp
    #convert to numeric for amounts 
    dfj["amount_awarded"] = pd.to_numeric(dfj["amount_awarded"]) 
    dfj["poss_awarded"] = dfj["comments"].str.contains("POSS")
    #we want to plot data for each precinct on how much was awarded to plaintiffs and how many possesions 
    #build df for graph
    df_graph = pd.DataFrame()
    for i in range(1,6):
        #possesion break downs
        df_graph.at[i,"Possesion Awarded"] = len(dfj.loc[dfj["poss_awarded"]].loc[dfj["precinct"]==str(i)]) #this is not accurate
        #amount breakdowns
        df_graph.at[i,"Amount Awarded"] =  '${:,.2f}'.format(dfj.loc[(dfj["precinct"]==str(i)) & (dfj["judgement_for"]=="PLAINTIFF")]["amount_awarded"].sum())
        #judgement breakdowns
        df_graph.at[i,"Judgment For Plaintiff"] =  len(dfj.loc[(dfj["judgement_for"] == "PLAINTIFF") & (dfj["precinct"]==str(i))])
        df_graph.at[i,"Judgment For Defendant"] =  len(dfj.loc[(dfj["judgement_for"] == "DEFENDANT") & (dfj["precinct"]==str(i))])
        df_graph.at[i,"No Judgment"] =  len(dfj.loc[(dfj["judgement_for"] == "NO JUDGEMENT") & (dfj["precinct"]==str(i))])
        #total number of cases
        df_graph.at[i,"Total Number of cases"] = len(dfj.loc[dfj["precinct"]==str(i)])
    #bar chart for amount
    df_bar = df_graph[["Amount Awarded"]]
    fig = px.bar (
        df_bar,
        x = df_bar.index,
        y = "Amount Awarded",
        orientation = "v",
        title = "Amounts Awarded by Precinct"       
    ) 
    display[0].plotly_chart(fig)
    #make pie charts FIGURE OUT HOW TO STOP SORTING THESE
    df_pie = df_graph[["Judgment For Plaintiff","Judgment For Defendant","No Judgment"]].T
    for i in range(1,6):
        df_pc = df_pie[i]
        fig = px.pie(
            df_pc, 
            values = df_pc.values, 
            names = df_pc.index, 
            color = df_pc.values,
            color_discrete_map={"Judgment for Plaintiff":"red","Judgment for Defendant":"green","No Judgment":"blue"},
            title = f"Precinct {i} Case Outcomes"
        )
        display[(i)%2].plotly_chart(fig)
          
    display[0].write(df_graph)


def representation_data(df):
    display = st.beta_columns(2)
    display[0].markdown("## Representation Information")
    display[1].markdown("## ")
    df_graph = pd.DataFrame()
    for i in range(1,6):
        #Representation Break downs
        df_graph.at[i,"Plaintiffs Attorneys"] = len(df.loc[(df["attorneys_for_plaintiffs"]!= "PRO SE") & (df["attorneys_for_plaintiffs"]!="") & (df["precinct"]==str(i))])
        df_graph.at[i,"Defendants Attorneys"] = len(df.loc[(df["attorneys_for_defendants"]!= "PRO SE") & (df["attorneys_for_defendants"]!="") & (df["precinct"]==str(i))])
        df_graph.at[i,"Plaintiffs Pro Se"] =  len(df.loc[(df["attorneys_for_plaintiffs"]== "PRO SE") & (df["attorneys_for_plaintiffs"]!="") & (df["precinct"]==str(i))])
        df_graph.at[i,"Defendants Pro Se"] =  len(df.loc[(df["attorneys_for_defendants"]== "PRO SE") & (df["attorneys_for_defendants"]!="") & (df["precinct"]==str(i))])
        df_graph.at[i,"Plaintiffs No Rep"] =  len(df.loc[(df["attorneys_for_defendants"]=="") & (df["precinct"]==str(i))])
        df_graph.at[i,"Defendants No Rep"] =  len(df.loc[(df["attorneys_for_defendants"]=="") & (df["precinct"]==str(i))])
        #total number of cases
        df_graph.at[i,"Total Number of cases"] = len(df.loc[df["precinct"]==str(i)])
    display[0].markdown("### Representation Counts")
    fig = px.bar(df_graph,x=df_graph.index,y=["Defendants Attorneys","Plaintiffs Attorneys","Defendants Pro Se","Plaintiffs Pro Se"])
    display[0].write(df_graph)
    display[0].markdown("### Representation Bar Graph")
    display[0].plotly_chart(fig)
    #top plaintiff attorneys
    df_a = df[(df["attorneys_for_plaintiffs"]!="PRO SE") & (df["attorneys_for_plaintiffs"]!="")]
    df_af = df_a.groupby("attorneys_for_plaintiffs").count()["case_number"].sort_values(ascending=False)
    display[1].markdown("### Top Plaintiff Attorneys")
    display[1].write(df_af)


def plaintiff_data(df_ef):
    #determine top plaintifss
    display = st.beta_columns(2)
    display[0].markdown("## Top Plaintiffs")
    display[1].markdown("## ")
    df = df_ef.groupby("plaintiff").count()["case_number"] 
    df= df.sort_values(ascending=False)
    display[0].write(df)
    pass    


def property_data(df_ef):
    display = st.beta_columns(2)
    display[0].markdown("## Property Data")
    display[1].markdown("## ")
    #determine top properties
    df_prop = df_ef[["parcel_id","code_complaints_count","code_violations_count","current_property_owner","dba","2016_unit_count","lon","lat"]]
    #get rid of unmatched entries
    df_prop = df_prop[df_prop["parcel_id"]!=""]
    #determine counts
    df1 = df_prop.groupby("parcel_id").count()["dba"]
    df1.columns = "Eviction Count"
    #get rid of duplicate ids since we already counted them
    df_props = df_prop.drop_duplicates("parcel_id")
    #merge counts back in and create final data frame    
    df_props = df_props.merge(df1,left_on="parcel_id",right_index=True) 
    #drop uneeded columns and rename
    df_pf = df_props[["dba_x","dba_y","parcel_id"]]
    df_pf.columns = ["DBA","Eviction Count","Parcel ID"]
    df_pf.sort_values("Eviction Count",ascending=False,inplace=True)

    #sort and take top 25
    display[0].markdown("## Top Properties by Eviction")
    display[0].write(df_pf)
    #map properties?
    df_props["lon"] = pd.to_numeric(df_props["lon"])
    df_props["lat"] = pd.to_numeric(df_props["lat"])
    #clean up +/-2 degress is probablt too much  
    df_props = df_props[(df_props["lat"]>28) & (df_props["lat"]<32)] 
    df_props = df_props[(df_props["lon"]>-99) & (df_props["lon"]<-95)] 
    display[1].markdown("### Map of Evictions in Austin")
    display[1].map(df_props,9)


def subsidy_data(df_ef):
    cols = st.beta_columns(2)
    display[0].markdown("## Property Subsidy Information")
    display[1].markdown("## ")
    #HACA is Has Sec 8 Voucher
    df = df_ef.loc[(df_ef["HACA"]=="TRUE") | (df_ef["CARES"]=="TRUE") | (df_ef["nhpd_property_id"]!="") ]
    df = pd.DataFrame(df
        .groupby('parcel_id')['case_number']
        .nunique()
    )    
    df_props = df_ef[["dba","parcel_id"]]
    df = df.merge(df_props,left_index=True,right_on="parcel_id")
    df.drop_duplicates("parcel_id",inplace=True)
    df.sort_values("case_number",ascending=False,inplace=True)
#    df.columns = ["Cases with Subsidies"]
    cols[0].markdown("### Subsidized Properties by Eviction Counts")
    cols[0].write(df)
    fig = px.bar (
        df.iloc[0:10,:],
        x = "dba",
        y = "case_number",
        orientation = "v",
    )
    cols[1].markdown("### Top 10 Subsidized Properties by Eviction Counts")
    cols[1].plotly_chart(fig) 
    #pie chart subsidy vs not
    df = df_ef.loc[(df_ef["HACA"]=="TRUE") | (df_ef["CARES"]=="TRUE") | (df_ef["nhpd_property_id"]!="") ] 
    df_not = df_ef.loc[(df_ef["HACA"]!="TRUE") & (df_ef["CARES"]!="TRUE") & (df_ef["nhpd_property_id"]=="") ] 
    df_pie = pd.DataFrame()
    df_pie.at["Subsidized","Count"] = len(df) 
    df_pie.at["Non-Subsidized","Count"] = len(df_not) 
    fig = px.pie(
        df_pie, 
        values="Count", 
        names=df_pie.index, 
    )
    cols[0].markdown("### Subsidized Properties Evictions vs. Non-Subsidized Properties")
    cols[0].plotly_chart(fig)
         

def eviction_data(df_e,df_s):
    with st.beta_expander("Eviction Data"):
        #Settings data 
        setting_data(df_s)       
        
        try:
            min_date = (
                df_e["date_filed"].min()-timedelta(days=7)
            )
        except: #happens when nulls are in court_date column
            min_date = df_e["date_filed"].iloc[0]
        max_date = datetime.today().date()+timedelta(days=90)
        start_date,end_date = date_options(
            min_date,max_date,"2"
        ) 
        
        
        #Filter data by date
        df_ef = filter_dates(
            df_e,
            start_date,
            end_date,
            "date_filed"
        )
        cols = st.beta_columns(2)
        if cols[0].checkbox("Judge Filing Data (click to expand)"):
            judge_data_filings(df_ef)
        if cols[1].checkbox("Judgement Data (click to expand)"):
            judgement_data(df_ef)
        if cols[0].checkbox("Plaintiff Data (click to expand)"):
            plaintiff_data(df_ef)
        if cols[1].checkbox("Representation (Attorney) Data (click to expand)"):
            representation_data(df_ef)
        if cols[0].checkbox("Property Data (click to expand)"):
            property_data(df_ef)
        if cols[1].checkbox("Subsidy Data (click to expand)"):
            subsidy_data(df_ef)


def render_page(df,df_e,df_s,df_c):
    """Render all page elements except the api key login"""
    #Clean data and convert types
    df = clean_df(df)
    df_s = clean_df(df_s)
    df_c = clean_df(df_c)
    df_e = clean_df(df_e)
    df = convert_date(df,"court_date")
    df_s = convert_date(df_s,"setting_date")
    df_e = convert_date(df_e,"hearing_date") 
    df_e = convert_date(df_e,"date_filed") #file date to date
     
    court_tracking_data(df,df_s,df_e)
    eviction_data(df_e,df_s)
#    st.write(df)


if __name__ == "__main__":
     if LOCAL:
         df = pd.read_csv("../data/01_Community_lawyer_test_out_final - Backend.csv")
         df_e = pd.read_csv("../data/Court_scraper_evictions_archive - evictions_archive.csv")
         df_s = pd.read_csv("../data/Court_scraper_eviction_scheduler - eviction_scheduler.csv")
         df_c = pd.read_csv("../data/Court_contact_data_PIR.csv")
         render_page(df,df_e,df_s,df_c)
     else:
         creds = st_config()
         if creds is not None:
                 df = copy.deepcopy(read_data(
                     creds,
                     "01_Community_lawyer_test_out_final",
                     "Frontend"
                 ))
                 df_e = copy.deepcopy(read_data(
                     creds,
                     "Back_end_eviction_data_2015_2021",
                     0
                 ))
                 df_s = copy.deepcopy(read_data(
                     creds,
                     "Court_scraper_eviction_scheduler",
                     "eviction_scheduler"
                 ))
                 df_c = copy.deepcopy(read_data(
                     creds,
                     "Court_contact_data_PIR",
                     0
                 ))
                 render_page(df,df_e,df_s,df_c)
         else:
             caching.clear_cache()
             st.text(f"Invalid password.")


