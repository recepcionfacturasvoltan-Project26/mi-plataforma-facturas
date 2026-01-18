import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Validador Voltan Group", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---

def extraer_datos_xml(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        }
        ruc = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID', ns).text
        monto = float(root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text)
        folio = root.find('cbc:ID', ns).text
        return {"ruc": ruc, "monto": monto, "folio": folio}
    except:
        return None

def buscar_texto_en_pdf(pdf_file, patron_regex):
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() or ""
        
        # Buscamos el patrón (ejemplo: un número de OC)
        resultado = re.search(patron_regex, texto_completo, re.IGNORECASE)
        return resultado.group(0) if resultado else "No encontrado"

# --- INTERFAZ ---
st.title("🇵🇪 Sistema de Validación de Compras")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Carga de Archivos")
    f_xml = st.file_uploader("XML de la Factura", type=["xml"])
    f_pdf = st.file_uploader("PDF de la Factura", type=["pdf"])
    f_oc = st.file_uploader("PDF de la Orden de Compra", type=["pdf"])
    
    # Campo para que el usuario diga cómo empieza su número de OC (ejemplo: OC- o 2024-)
    patron_oc = st.text_input("Patrón de número de OC (Ejemplo: OC-\d+)", value="OC-\d+")

with col2:
    st.header("2. Resultado de Validación")
    if st.button("Validar Documentación"):
        if f_xml and f_pdf and f_oc:
            # 1. Obtener datos del XML
            datos_xml = extraer_datos_xml(f_xml)
            
            # 2. Buscar OC dentro del PDF de la Factura
            oc_en_factura = buscar_texto_en_pdf(f_pdf, patron_oc)
            
            # 3. Buscar OC dentro del PDF de la Orden de Compra
            oc_en_documento_oc = buscar_texto_en_pdf(f_oc, patron_oc)
            
            # --- MOSTRAR RESULTADOS ---
            st.write(f"**Factura:** {datos_xml['folio']} | **Monto:** S/ {datos_xml['monto']}")
            st.write(f"**OC detectada en Factura:** {oc_en_factura}")
            st.write(f"**OC detectada en Documento OC:** {oc_en_documento_oc}")
            
            st.divider()
            
            # Lógica de semáforo
            if oc_en_factura == oc_en_documento_oc and oc_en_factura != "No encontrado":
                st.success("✅ ¡COINCIDENCIA TOTAL! La factura corresponde a la orden de compra.")
                st.balloons()
            else:
                st.error("❌ ERROR DE CONCORDANCIA: Los números de OC no coinciden o no se encontraron.")
        else:
            st.warning("Asegúrate de subir los 3 archivos.")
