import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import datetime
from plotly.subplots import make_subplots
import plotly.express as px

HUCKLEBERRY_DIR = Path("./huckleberry_data_dumps")

def time_to_mins(time):
    hours,minutes = time.split(":")
    
    return float(hours)*60+float(minutes)

def volume_plot(pumping,norm_pumping, rolling_avg=False,rolling_step=7, split_by_pump_type = False, per_session = False):
    per_session = per_session == "Per Session"
    norm_pumping = norm_pumping == "Yes"
    split_by_pump_type = split_by_pump_type == "Yes"
    pumping["time"] = pd.to_datetime(pumping["Start"])
    pumping["date"] = pumping["time"].apply(lambda x:x.date())
    if per_session:
        pumping["date"] = list(pumping.index)[::-1]
    pumping["left_ml"] = pumping["Start Condition"].apply(lambda x:float(x[:-2]))
    pumping["right_ml"] = pumping["End Condition"].apply(lambda x:float(x[:-2]))
    pumping["total_ml"] = pumping["left_ml"] + pumping["right_ml"]
    pumping["pump_type"] = pumping["Notes"].apply(lambda x: np.nan if type(x)!=str else "Elvie" if "elvie" in x.lower() else "Spectra" if "spectra" in x.lower() else np.nan)

    pumping_melt = pumping.melt(id_vars=[x for x in pumping if "_ml" not in x],var_name="breast",value_name="volume(ml)")
    pumping_melt = pumping_melt[pumping_melt["volume(ml)"]!=0]
    if split_by_pump_type:
        group_cols_volume = ["date","breast","pump_type"]
        group_cols_duration = ["date","pump_type"]
        rolling_volume_group_cols = ["breast","pump_type"]
        duration_columns = ["Duration","date","pump_type"]
        merge_on = ["date","pump_type"]
        color_col = "breast: pump"
        duration_color = "pump_type"
    else:
        rolling_volume_group_cols = ["breast"]
        group_cols_volume = ["date","breast"]
        group_cols_duration = ["date"]
        duration_columns = ["Duration","date"]
        merge_on = ["date"]
        color_col = "breast"
        duration_color = None
        
    agg_by_breast = pumping_melt.groupby(group_cols_volume)[["volume(ml)"]].agg(sum).reset_index()

    agg_by_duration = pumping[duration_columns].dropna()
    agg_by_duration["Duration"] = agg_by_duration["Duration"].apply(time_to_mins)
    agg_by_duration = agg_by_duration.groupby(group_cols_duration).agg(sum).reset_index()

    if rolling_avg:
        rolling_avg = []
        rolling_duration = []
        for group,subdf in agg_by_breast.groupby(rolling_volume_group_cols):
            for i in range(rolling_step,len(subdf)):
                next_step = [subdf.iloc[i]["date"],subdf.iloc[i:i+rolling_step]["volume(ml)"].mean()]
                if type(group) == tuple:
                    next_step.extend(group)
                else:
                    next_step.append(group)
                
                rolling_avg.append(next_step)
        
        agg_by_breast = pd.DataFrame(rolling_avg,columns=["date","volume(ml)"]+rolling_volume_group_cols)

        if split_by_pump_type:
            for pump_type,subdf in agg_by_duration.groupby("pump_type"):
                for i in range(rolling_step,len(subdf)):
                    rolling_duration.append((subdf.iloc[i]["date"],subdf.iloc[i:i+rolling_step]["Duration"].mean(),pump_type))
            agg_by_duration = pd.DataFrame(rolling_duration,columns=["date","Duration","pump_type"])
        else:
            for i in range(rolling_step,len(agg_by_duration)):
                rolling_duration.append((agg_by_duration.iloc[i]["date"],agg_by_duration.iloc[i:i+rolling_step]["Duration"].mean()))
            agg_by_duration = pd.DataFrame(rolling_duration,columns=["date","Duration"])        

    if norm_pumping:
        plot_frame = agg_by_duration.merge(agg_by_breast,on=merge_on)
        plot_frame["volume(ml)/min"] = plot_frame["volume(ml)"] / plot_frame["Duration"]
        y_axis = "volume(ml)/min"
    else:
        plot_frame = agg_by_breast
        y_axis = "volume(ml)"

    if split_by_pump_type:
        plot_frame["breast: pump"] = plot_frame["breast"] + ": " + plot_frame["pump_type"]

    
    fig = px.line(
        data_frame = plot_frame,
        x = "date",
        y = y_axis,
        color = color_col,
        width = 1000,
        height = 500,
        markers = True,
    )
    if norm_pumping:
        subfig = fig
    
    if not norm_pumping:
        fig2 = px.line(
            data_frame = agg_by_duration,
            x = "date",
            y = "Duration",
            color = duration_color,
            width = 1000,
            height = 500,
        )
        
        fig2.update_traces(yaxis="y2")
        
        for trace in fig2.data:
            if not split_by_pump_type:
                trace['line']['color']='grey'
            trace['line']['dash']='dash'
            trace['name']=trace["legendgroup"]+': Duration'
            trace['showlegend']=True
        
        subfig = make_subplots(specs=[[{"secondary_y": True}]])
        subfig.add_traces(fig.data + fig2.data)
        subfig.layout.xaxis.title="Date"
        subfig.layout.yaxis.title="Volume (mL)"
        subfig.layout.yaxis2.title="Duration (min)"
        subfig.layout.width = 1100
        subfig.layout.height = 500
    st.write(subfig)

def feeding_duration_plot(pumping,feeding):
    agg = pumping[["Duration","date"]].dropna()
    agg["Duration"] = agg["Duration"].apply(time_to_mins)
    agg = agg.groupby(["date"]).agg(sum).reset_index()
    feeding = feeding[feeding['Start Location']=="Breast"]
    feeding["time"] = pd.to_datetime(feeding["Start"])
    feeding["date"] = feeding["time"].apply(lambda x:x.date())
    agg2 = feeding[["Duration","date"]].dropna()
    agg2["Duration"] = agg2["Duration"].apply(time_to_mins)
    agg2 = agg2.groupby(["date"]).agg(sum).reset_index()

    agg["Type"] = "pumping"
    agg2["Type"] = "nursing/SNS"
    
    comp = agg.merge(agg2,on="date")
    comp["Duration"] = comp["Duration_x"]+comp["Duration_y"]
    comp["Type"] = "Both Combined"
    
    combined = pd.concat([agg,agg2,comp])
    fig = px.line(
        data_frame = combined,
        x = "date",
        y = "Duration",
        color = "Type",
        width = 1000,
        height = 500,
        markers = True,
        labels = {"Duration":"Total Time (minutes)"}
    )
    
    st.write(fig)

def breast_milk_page():
    st.title("Huckleberry Dashboard")
    st.header("Data Management")
    
    existing_file_or_upload_cols = st.columns(2)

    with existing_file_or_upload_cols[0]:
        data_sets = [x.stem for x in HUCKLEBERRY_DIR.iterdir()]
        chosen_date = st.selectbox(label = "Select Dataset Date", options = data_sets)
        chosen_dataset = pd.read_csv(HUCKLEBERRY_DIR / f"{chosen_date}.csv")

    with existing_file_or_upload_cols[1]:
        upload_huckleberry_csv = st.file_uploader(label = "Upload new huckleberry csv", type = "csv")
        if st.button("Upload Data"):
            if upload_huckleberry_csv is not None:
                chosen_dataset = pd.read_csv(upload_huckleberry_csv)
                chosen_dataset.to_csv(HUCKLEBERRY_DIR / f"{datetime.date.today()}.csv")

    pumping = chosen_dataset[chosen_dataset["Type"]=="Pump"]
    feeding = chosen_dataset[chosen_dataset["Type"]=="Feed"]
    
    st.header("Per Timepoint Plots")
    
    st.subheader("Pumping")
    pump_cols = st.columns(3)
    with pump_cols[0]:
        norm_pumping = st.radio(label="Normalize To Duration",options = ["Yes","No"],horizontal=True)
    with pump_cols[1]:
        split_by_pump_type = st.radio(label="Split By Pump Type",options = ["Yes","No"],index=1,horizontal=True)
    with pump_cols[2]:
        per_session_or_per_date = st.radio(label="X Axis Time Unit",options = ["Per Day","Per Session"],index=0,horizontal=True)
    volume_plot(pumping,norm_pumping, split_by_pump_type = split_by_pump_type, per_session = per_session_or_per_date)
    
    st.subheader("Total Nipple Simulation")
    feeding_duration_plot(pumping,feeding)

    st.header("Rolling Timewindow Plots")
    st.subheader("Pumping")
    pump_cols_rolling = st.columns(3)
    with pump_cols_rolling[0]:
        norm_pumping_window = st.radio(label="Normalize To Duration",options = ["Yes","No"],horizontal=True, key = "norm_pumping_window")
    with pump_cols_rolling[1]:
        split_by_pump_type_window = st.radio(label="Split By Pump Type",options = ["Yes","No"],index=1,horizontal=True, key = "split_pumping_window")
    with pump_cols_rolling[2]:
        per_session_or_per_date_rolling = st.radio(label="X Axis Time Unit",options = ["Per Day","Per Session"],index=0,horizontal=True, key = "per_session_or_per_date_rolling")
    
    rs_slider_col = st.columns(2)
    with rs_slider_col[0]:
        rolling_step_slider = st.slider(label = "How Many Days To Average", step=1,min_value=5, max_value = 14, value=7)
    
    volume_plot(pumping,norm_pumping_window,rolling_avg = True, rolling_step = rolling_step_slider, split_by_pump_type = split_by_pump_type_window, per_session = per_session_or_per_date_rolling)