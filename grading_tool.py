import streamlit as st
import pandas as pd

st.write("Hello! This is the start of a new project")

x = st.text_input("what is your favourite movie?")
st.write(f"Your favourite movie is {x}")

df = pd.read_csv('data.csv')

st.dataframe(df)


para = df.agg(['mean','median','std','min','max'])
# print(para)
st.write(para)

para = df.agg({
    'Accelerometer 1 (m/s^2)' : ['mean','median'],
    'Microphone (V)' : ['std','min'],
    'Temperature (Celsius)' : ['count','max']})
# print(para)
st.write(para)

mean = df['Temperature (Celsius)'].mean()
median = df['Temperature (Celsius)'].median()
max = df['Temperature (Celsius)'].max()

col1,col2,col3 = st.columns(3)

col1.metric(label="Mean Val", value = f"${mean:.2f}")
col2.metric(label="Mean Val", value = median)
col3.metric(label="Mean Val", value = max)

st.write(df.median())
# st.write(type(df.mean()))
st.write(df.median())
st.write(df.std())
st.write(df.min())
st.write(df.max())

st.dataframe(df.head())
st.write(df.describe())




st.title("Upload your File")

file = st.file_uploader("Choose your CSV file", type = "csv")

if file is not None:
    df1 = pd.read_csv(file)
    st.write("Your csv file :")
    st.dataframe(df1)
