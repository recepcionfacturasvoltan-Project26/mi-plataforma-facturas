import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Control de Facturas - Voltan Group", layout="wide")

# --- FUNCIONES LÓGICAS ---

def normalizar_oc(texto):
    if not texto or "No" in texto: return "No encontrado"
    # Extraer solo números y guiones, y quitar ceros a la izquierda
    limpio = re.sub(r'[^0-9-]', '', texto)
    if '-' in limpio:
        return "-".join([str(int(p)) for p in limpio.split('-') if p.isdigit()])
    return str(int(limpio)) if limpio.isdigit() else limpio

def extraer_oc_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "".join([p.extract_text() or "" for p in pdf.pages])
        # Busca patrones como OC: 001-45, Orden de Compra 00023, etc.
        patron = r"(?:ORDEN DE COMPRA|OC|O/C|SERVICIO)[:\s-]*(\d+(?:-\d+)?)"
        match = re.search(patron, texto, re.IGNORECASE)
        return match.group(1) if match else "No encontrado"

# --- INTERFAZ ---
st.title("🛡️ Sistema de Validación Voltan Group")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📁 Cargar Documentos")
    f_xml = st.file_uploader("XML Factura (SUNAT)", type=["xml"])
    f_pdf = st.file_uploader("PDF Factura", type=["pdf"])
    f_oc = st.file_uploader("PDF Orden de Compra", type=["pdf"])

with col2:
    st.subheader("📋 Resultado del Análisis")
    if st.button("EJECUTAR VALIDACIÓN"):
        if f_xml and f_pdf and f_oc:
            # 1. Procesar XML para datos generales
            tree = ET.parse(f_xml)
            root = tree.getroot()
            ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                  'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
            
            prov = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns).text
            monto = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text
            
            # 2. Lógica de OC
            oc_en_factura = extraer_oc_pdf(f_pdf)
            oc_en_documento = extraer_oc_pdf(f_oc)
            
            val_factura = normalizar_oc(oc_en_factura)
            val_documento = normalizar_oc(oc_en_documento)
            
            # --- CAMPO DE VALIDACIÓN (SEMÁFORO) ---
            st.write(f"**Proveedor:** {prov} | **Monto:** S/
