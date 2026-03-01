import streamlit as st
import pandas as pd
import sqlite3
from bs4 import BeautifulSoup as bs
from requests import get
import time
import os

# ------------------ CONFIG APP ------------------ #
st.markdown("<h1 style='text-align: center; color: black;'>DATA SCRAPER CoinAfrique</h1>", unsafe_allow_html=True)
st.markdown("""
Cette app vous permet de scraper et télécharger les données sur les vêtements 
et les chaussures des hommes et des enfants à partir du site CoinAfrique.
* Python libraries: bs4, pandas, streamlit
* Data source: CoinAfrique SN (https://sn.coinafrique.com/)
""")

st.markdown("""
<style>
[data-testid="stDataFrame"] div[role="grid"] {
    background-color: white;
}
[data-testid="stDataFrame"] thead th div {
    font-weight: 800;
    font-size: 15px;
}
</style>
""", unsafe_allow_html=True)

# ------------------ Base de Données ------------------ #
def init_db():
    conn = sqlite3.connect('coinafrique.db', check_same_thread=False)
    c = conn.cursor()
    tables = ['DATA_table1', 'DATA_table2', 'DATA_table3', 'DATA_table4']
    for table in tables:
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} 
            (type_chaussure TEXT,
             type_habit TEXT,
             prix TEXT,
             adresse TEXT,
             image_lien TEXT,
             page INT,
             categorie TEXT)
        ''')
    conn.commit()
    return conn

def load_data(categorie, max_pages):
    conn = init_db()
    table_num = {
        'vetements-homme': 'DATA_table1',
        'chaussures-homme': 'DATA_table2',
        'vetements-enfants': 'DATA_table3',
        'chaussures-enfants': 'DATA_table4'
    }
    table_name = table_num[categorie]

    # écraser les anciens résultats pour cette catégorie
    c = conn.cursor()
    c.execute(f'DELETE FROM {table_name}')
    conn.commit()

    df_final = pd.DataFrame()
    for p in range(1, max_pages + 1):
        url = f'https://sn.coinafrique.com/categorie/{categorie}?page={p}'
        res = get(url)
        soup = bs(res.content, 'html.parser')
        containers = soup.find_all('div', class_='col s6 m4 l3')
        data = []

        for container in containers:
            try:
                desc = container.find('p', class_='ad__card-description').text.strip()
                prix = container.find('p', class_='ad__card-price').text.strip('CFA') if container.find('p', class_='ad__card-price') else 'N/A'
                adresse = container.find('p', class_='ad__card-location').text.replace('location_on','').strip() if container.find('p', class_='ad__card-location') else 'N/A'
                img = container.find('img')
                image_lien = img['src'] if img else 'N/A'

                if 'chaussures' in categorie:
                    type_chaussure = desc
                    type_habit = ''
                    type_col = 'Type chaussure'
                    type_value = type_chaussure
                else:
                    type_chaussure = ''
                    type_habit = desc
                    type_col = 'Type habit'
                    type_value = type_habit

                # enregistrement de la Base de données
                c.execute(
                    f'INSERT INTO {table_name} VALUES (?,?,?,?,?,?,?)',
                    (type_chaussure, type_habit, prix, adresse, image_lien, p, categorie)
                )
                conn.commit()

                dic = {
                    type_col: type_value,
                    'Prix': prix,
                    'Adresse': adresse,
                    'Image lien': image_lien
                }
                data.append(dic)
            except:
                continue

        DF_page = pd.DataFrame(data)
        df_final = pd.concat([df_final, DF_page], ignore_index=True)
        time.sleep(1)

    conn.close()
    return df_final

def save_to_csv(df, filename):
    os.makedirs('data', exist_ok=True)
    filepath = os.path.join('data', filename)
    df.to_csv(filepath, index=False)

# ------------------ SIDEBAR ------------------ #
st.sidebar.title("Options")
option = st.sidebar.selectbox("Choisir :", ["Scraper", "Dashboard", "Télécharger", "Évaluer l'App"])
max_pages = st.sidebar.number_input("Nb Pages", value=1, min_value=1, max_value=10)

categories = ['vetements-homme', 'chaussures-homme', 'vetements-enfants', 'chaussures-enfants']

# ------------------ SCRAPER ------------------ #
if option == "Scraper":
    st.header("Scraping)
    for cat in categories:
        if st.button(cat.replace('-', ' ').title()):
            df = load_data(cat, max_pages)

            st.write(f"Dimension : {df.shape[0]} lignes et {df.shape[1]} colonnes")
            st.dataframe(df)

# ------------------ DASHBOARD ------------------ #
elif option == "Dashboard":
    st.header("Dashboard")

    # 2 lignes, 2 colonnes
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    dash_info = [
        ("Vêtement enfant", "vetement_enfant_clean.csv", row1_col1),
        ("Vêtement homme", "vetement_homme_clean.csv", row1_col2),
        ("Chaussure enfant", "chaussure_enfant_clean.csv", row2_col1),
        ("Chaussure homme", "chaussure_homme_clean.csv", row2_col2),
    ]

    for title, fname, col in dash_info:
        path = os.path.join('data', fname)

        with col:
            st.subheader(title)

            if os.path.exists(path):

                df = pd.read_csv(path)

                # ----------- Création colonne Type ----------- #
                if 'type chaussure' in df.columns:
                    df['Type'] = df['type chaussure']
                elif 'type habits' in df.columns:
                    df['Type'] = df['type habits']
                else:
                    df['Type'] = "Non défini"

                df['Type'] = df['Type'].fillna("Non défini")

                # ----------- Conversion prix ----------- #
                df['Prix_num'] = pd.to_numeric(df['prix'], errors='coerce')

                if df['Prix_num'].dropna().empty:
                    st.write("Pas de prix disponible")
                    continue

                # ----------- TRAITEMENT DES VALEURS ABERRANTES (IQR) ----------- #
                prix_clean = df['Prix_num'].dropna()

                Q1 = prix_clean.quantile(0.25)
                Q3 = prix_clean.quantile(0.75)
                IQR = Q3 - Q1

                borne_inf = Q1 - 1.5 * IQR
                borne_sup = Q3 + 1.5 * IQR

                # moyenne des valeurs normales
                moyenne_normale = prix_clean[
                    (prix_clean >= borne_inf) & (prix_clean <= borne_sup)
                ].mean()

                # remplacement des outliers
                df['Prix_num'] = df['Prix_num'].apply(
                    lambda x: moyenne_normale if (x < borne_inf or x > borne_sup) else x
                )

                # ----------- Calcul min / moyen / max ----------- #
                idx_min = df['Prix_num'].idxmin()
                idx_max = df['Prix_num'].idxmax()
                

                prix_min = int(df.loc[idx_min, 'Prix_num'])
                prix_max = int(df.loc[idx_max, 'Prix_num'])
                prix_moy = int(df['Prix_num'].mean())

                type_min = df.loc[idx_min, 'Type']
                type_max = df.loc[idx_max, 'Type']
                type_mean = df['Type'].mode()
                
                if not type_mean.empty:
                    type_mean = type_mean[0] 
                else:
                    type_mean = "Non défini"
                # ----------- Tableau récapitulatif ----------- #
                recap = pd.DataFrame({
                    "Indicateur": ["Prix minimum", "Prix moyen", "Prix maximum"],
                    "Valeur (FCFA)": [
                        f"{prix_min:,.0f}",
                        f"{prix_moy:,.0f}",
                        f"{prix_max:,.0f}"
                    ],
                    "Type": [type_min, type_mean, type_max]
                })

                st.dataframe(recap, use_container_width=True)

                # ----------- Courbe variation selon types ----------- #
                prix_par_type = (
                    df.groupby('Type')['Prix_num']
                    .mean()
                    .sort_values()
                )

                st.caption("Variation du prix moyen selon le type")
                st.line_chart(prix_par_type)

            else:
                st.write("Fichier manquant")
                
# ------------------ TÉLÉCHARGER ------------------ #
elif option == "Télécharger":
    st.header("Téléchargement des Données au format CSV")

    boutons = [
        ("Vêtement homme", "vetements_homme.csv"),
        ("Vêtement enfant", "vetements_enfants.csv"),
        ("Chaussure homme", "chaussures_homme.csv"),
        ("Chaussure enfant", "chaussures_enfants.csv"),
    ]

    for label, filename in boutons:
        path = os.path.join('data', filename)
        if os.path.exists(path):
            if st.button(label):
                df = pd.read_csv(path)
                st.write(f"Dimension : {df.shape[0]} lignes et {df.shape[1]} colonnes")
                st.dataframe(df)

# ------------------ ÉVALUER ------------------ #
elif option == "Évaluer l'App":
    st.header("Évaluer l'Application")

    st.markdown(
    '<a href="https://ee.kobotoolbox.org/x/0Edv16tV" target="_blank">'
    '<button>Ouvrir KoboToolbox</button></a>',
    unsafe_allow_html=True
)

    st.markdown(
        '<a href="https://docs.google.com/forms/d/e/1FAIpQLSeMuz7iIWe06p5Tbb2R7tUVzCe3Z62VfPImZq3vWlfOYtGNIw/viewform?usp=publish-editor" target="_blank">'
        '<button>Ouvrir Google Forms</button></a>',
        unsafe_allow_html=True
    )

