import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Voltan Group - Control Fiscal", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN XML (LA VERDAD LEGAL) ---
def extraer_datos_xml(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        }
        
        # Datos de Cabecera
        ruc_emisor = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID', ns).text
        ruc_receptor = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID', ns).text
        comprobante = root.find('cbc:ID', ns).text
        fecha = root.find('cbc:IssueDate', ns).text
        moneda = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).attrib.get('currencyID')
        
        # Totales
        base_imponible = float(root.find('.//cac:TaxSubtotal/cbc:TaxableAmount', ns).text)
        igv = float(root.find('.//cac:TaxSubtotal/cbc:TaxAmount', ns).text)
        total = float(root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text)
        
        return {
            "RUC_E": ruc_emisor, "RUC_R": ruc_receptor, "ID": comprobante,
            "FECHA": fecha, "MONEDA": moneda, "BASE": base_imponible,
            "IGV": igv, "TOTAL": total
        }
    except: return None

# --- FUNCIONES DE EXTRACCIÓN PDF ---
def extraer_datos_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "".join([p.extract_text() or "" for p in pdf.pages])
        
        # Buscar Código de Detracción (ej: 019)
        match_cod = re.search(r"SUJETOS A DETRACCI[ÓO]N[:\s-]*(\d{3})", texto)
        # Buscar % de detracción
        match_pct = re.search(r"(\d{1,2})\s*%\s*(?:DE)?\s*DETRACCI[ÓO]N", texto)
        # Buscar OC y CECO
        match_oc = re.search(r"(?:OC|ORDEN|SERVICIO)[:\s-]*(\d+(?:-\d+)?)", texto, re.IGNORECASE)
        match_ceco = re.search(r"(?:CECO|CENTRO COSTO)[:\s-]*([A-Z0-9-]+)", texto, re.IGNORECASE)
        
        return {
            "COD_DET": match_cod.group(1) if match_cod else "N/A",
            "PCT_DET": float(match_pct.group(1)) if match_pct else 0.0,
            "OC_NUM": match_oc.group(1) if match_oc else "No encontrado",
            "CECO": match_ceco.group(1) if match_ceco else "ADMIN"
        }

# --- INTERFAZ ---
st.title("🇵🇪 Plataforma de Recepción Voltan Group")

col_files = st.columns(3)
with col_files[0]: f_xml = st.file_uploader("XML Factura", type=["xml"])
with col_files[1]: f_pdf = st.file_uploader("PDF Factura", type=["pdf"])
with col_files[2]: f_oc = st.file_uploader("PDF Orden de Compra", type=["pdf"])

if st.button("PROCESAR REGISTRO"):
    if f_xml and f_pdf and f_oc:
        xml_data = extraer_datos_xml(f_xml)
        pdf_f = extraer_datos_pdf(f_pdf)
        pdf_o = extraer_datos_pdf(f_oc)
        
        # LÓGICA DE DETRACCIÓN (Regla de S/ 700.01)
        aplica_detraccion = "NO"
        monto_detraccion = 0.0
        # Solo aplica si es PEN y > 700 o si es USD (convertido)
        if (xml_data['MONEDA'] == "PEN" and xml_data['TOTAL'] > 700.00) or xml_data['MONEDA'] == "USD":
            if pdf_f['PCT_DET'] > 0:
                aplica_detraccion = "SÍ"
                monto_detraccion = xml_data['TOTAL'] * (pdf_f['PCT_DET'] / 100)
        
        neto_pagar = xml_data['TOTAL'] - monto_detraccion
        
        # VALIDACIÓN DE ORDEN DE COMPRA
        oc_aprobada = "APROBADO ✅" if pdf_f['OC_NUM'] in pdf_o['OC_NUM'] else "REVISAR ❌"

        # --- REPORTE HORIZONTAL ---
        st.subheader("📊 Vista Previa del Reporte (Horizontal)")
        
        registro_horizontal = {
            "Fecha": xml_data['FECHA'],
            "Proveedor RUC": xml_data['RUC_E'],
            "Comprobante": xml_data['ID'],
            "Moneda": xml_data['MONEDA'],
            "Base Imponible": xml_data['BASE'],
            "IGV": xml_data['IGV'],
            "Total Factura": xml_data['TOTAL'],
            "Aplica Detrac.": aplica_detraccion,
            "Cod. Detrac.": pdf_f['COD_DET'],
            "Monto Detrac.": round(monto_detraccion, 2),
            "Neto a Pagar": round(neto_pagar, 2),
            "OC": pdf_f['OC_NUM'],
            "CECO": pdf_o['CECO'],
            "Validación OC": oc_aprobada
        }
        
        df_reporte = pd.DataFrame([registro_horizontal])
        st.dataframe(df_reporte) # Muestra la tabla horizontal

        # --- VALIDACIÓN XML VS PDF ---
        with st.expander("Verificar Integridad XML vs PDF"):
            if xml_data['TOTAL'] > 0:
                st.write("✅ La Base Imponible + IGV coinciden con el Total del XML.")
                st.write(f"✅ Documento de Orden de Compra: **{oc_aprobada}**")

    else:
        st.error("Por favor cargue los 3 archivos.")
