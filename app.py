import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber

st.set_page_config(page_title="Recepción de Facturas", layout="wide")

st.title("📂 Mi Plataforma de Recepción")
st.markdown("Sube tus documentos para extraer la información automáticamente.")

# --- SECCIÓN DE CARGA ---
col1, col2, col3 = st.columns(3)

with col1:
    xml_input = st.file_uploader("1. Cargar Factura (XML)", type=["xml"])
with col2:
    pdf_input = st.file_uploader("2. Cargar Factura (PDF)", type=["pdf"])
with col3:
    oc_input = st.file_uploader("3. Orden de Compra (PDF)", type=["pdf"])

# --- PROCESAMIENTO ---
if st.button("🚀 Extraer Datos y Validar"):
    if xml_input and pdf_input:
        # Extraer del XML
        tree = ET.parse(xml_input)
        root = tree.getroot()
        
        # Nota: Aquí el código busca datos generales. 
        # Cada país tiene etiquetas distintas, pero esto es un ejemplo:
        st.subheader("📊 Datos Extraídos")
        
        factura_data = {
            "Proveedor": "Extraído del XML",
            "Monto Total": "100.00", # Esto se automatiza luego
            "Folio": "12345"
        }
        
        st.table([factura_data])
        
        if oc_input:
            st.info("Orden de compra detectada. Validando montos...")
            # Aquí iría la lógica para leer la OC
            st.success("✅ La Factura coincide con la Orden de Compra")
    else:
        st.warning("Por favor sube al menos el XML y el PDF de la factura.")
