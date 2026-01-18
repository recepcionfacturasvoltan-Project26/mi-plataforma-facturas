import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Control de Facturas - Voltan Group", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN MEJORADAS ---

def normalizar_oc(texto):
    if not texto or "No" in str(texto): return "No encontrado"
    limpio = re.sub(r'[^0-9-]', '', str(texto))
    if '-' in limpio:
        try:
            return "-".join([str(int(p)) for p in limpio.split('-') if p.isdigit()])
        except: return limpio
    return str(int(limpio)) if limpio.isdigit() else limpio

def extraer_datos_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            texto = "".join([p.extract_text() or "" for p in pdf.pages])
            
            # 1. Buscar Orden de Compra
            patron_oc = r"(?:ORDEN DE COMPRA|OC|O/C|SERVICIO)[:\s-]*(\d+(?:-\d+)?)"
            match_oc = re.search(patron_oc, texto, re.IGNORECASE)
            oc = match_oc.group(1) if match_oc else "No encontrado"
            
            # 2. Buscar Centro de Costo (Busca la palabra y captura lo que sigue)
            # Este patrón busca "Centro de Costo", "CECO" o "C. Costo"
            patron_ceco = r"(?:CENTRO DE COSTO|CECO|C\. COSTO)[:\s-]*([A-Z0-9\s-]+)"
            match_ceco = re.search(patron_ceco, texto, re.IGNORECASE)
            ceco = match_ceco.group(1).strip().split('\n')[0] if match_ceco else "No especificado"
            
            return {"oc": oc, "ceco": ceco}
    except:
        return {"oc": "Error", "ceco": "Error"}

# --- INTERFAZ ---
st.title("🛡️ Sistema de Validación Voltan Group")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📁 Cargar Documentos")
    f_xml = st.file_uploader("1. XML Factura (SUNAT)", type=["xml"])
    f_pdf = st.file_uploader("2. PDF Factura", type=["pdf"])
    f_oc = st.file_uploader("3. PDF Orden de Compra", type=["pdf"])

with col2:
    st.subheader("📋 Resultado del Análisis")
    if st.button("EJECUTAR VALIDACIÓN"):
        if f_xml and f_pdf and f_oc:
            try:
                # Procesar XML
                tree = ET.parse(f_xml)
                root = tree.getroot()
                ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
                
                prov = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns).text
                monto = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text
                
                # Procesar PDFs
                datos_factura = extraer_datos_pdf(f_pdf)
                datos_oc = extraer_datos_pdf(f_oc)
                
                val_oc_factura = normalizar_oc(datos_factura['oc'])
                val_oc_documento = normalizar_oc(datos_oc['oc'])
                
                # --- VISUALIZACIÓN DE RESULTADOS ---
                st.info(f"**Proveedor:** {prov} | **Monto:** S/ {monto}")
                
                # Fila de Validación de OC
                if datos_factura['oc'] == "No encontrado":
                    st.warning("⚠️ OC EN FACTURA: NO SE ENCONTRÓ REGISTRO")
                elif val_oc_factura == val_oc_documento:
                    st.success(f"✅ OC: COINCIDE ({val_oc_factura})")
                else:
                    st.error(f"❌ OC: NO COINCIDE (Factura: {datos_factura['oc']} | OC: {datos_oc['oc']})")

                # Fila de Centro de Costo
                st.markdown(f"**Centro de Costo Detectado en OC:** `{datos_oc['ceco']}`")
                
                # Tabla resumen final
                resumen = {
                    "Campo": ["Orden de Compra", "Centro de Costo", "Monto", "Proveedor"],
                    "Dato en Factura": [datos_factura['oc'], "No aplica", f"S/ {monto}", prov],
                    "
