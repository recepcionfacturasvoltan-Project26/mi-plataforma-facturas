import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Voltan Group - Recepción Pro", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---

def extraer_datos_xml(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        }
        return {
            "RUC_E": root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID', ns).text,
            "RAZON_SOCIAL": root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns).text,
            "RUC_R": root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID', ns).text,
            "ID": root.find('cbc:ID', ns).text,
            "FECHA": root.find('cbc:IssueDate', ns).text,
            "MONEDA": "PEN" if "PEN" in root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).attrib.get('currencyID') else "USD",
            "BASE": float(root.find('.//cac:TaxSubtotal/cbc:TaxableAmount', ns).text),
            "IGV": float(root.find('.//cac:TaxSubtotal/cbc:TaxAmount', ns).text),
            "TOTAL": float(root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text)
        }
    except: return None

def extraer_datos_pdf_factura(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "".join([p.extract_text() or "" for p in pdf.pages])
        # Buscar código de detracción (3 dígitos) y porcentaje
        match_cod = re.search(r"DETRACCI[ÓO]N[:\s-]*(\d{3})", texto)
        match_pct = re.search(r"(\d{1,2})\s*%\s*(?:DE)?\s*DETRACCI[ÓO]N", texto)
        match_oc = re.search(r"(?:OC|ORDEN|SERVICIO)[:\s-]*(\d+(?:-\d+)?)", texto, re.IGNORECASE)
        
        return {
            "COD_DET": match_cod.group(1) if match_cod else "N/A",
            "PCT_DET": float(match_pct.group(1)) if match_pct else 0.0,
            "OC_REF": match_oc.group(1) if match_oc else "No encontrado"
        }

def extraer_datos_pdf_oc(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "".join([p.extract_text() or "" for p in pdf.pages])
        # Condición de Pago
        match_pago = re.search(r"COND\.\s*PAGO[:\s-]*([A-Z0-9\s]+)", texto, re.IGNORECASE)
        # Situación de la OC
        match_situacion = re.search(r"SITUACI[ÓO]N\s*[:\s-]*([A-ZÁÉÍÓÚ]+)", texto, re.IGNORECASE)
        # Centro de Costo
        match_ceco = re.search(r"(?:CECO|CENTRO COSTO)[:\s-]*([A-Z0-9-]+)", texto, re.IGNORECASE)
        
        return {
            "COND_PAGO": match_pago.group(1).strip() if match_pago else "No encontrado",
            "SITUACION": match_situacion.group(1).strip() if match_situacion else "PENDIENTE",
            "CECO": match_ceco.group(1).strip() if match_ceco else "ADMIN"
        }

# --- INTERFAZ ---
st.title("🇵🇪 Reporte Horizontal de Recepción - Voltan Group")

f_xml = st.file_uploader("Cargar XML Factura", type=["xml"])
f_pdf = st.file_uploader("Cargar PDF Factura", type=["pdf"])
f_oc = st.file_uploader("Cargar PDF Orden de Compra", type=["pdf"])

if st.button("GENERAR REPORTE HORIZONTAL"):
    if f_xml and f_pdf and f_oc:
        x = extraer_datos_xml(f_xml)
        pf = extraer_datos_pdf_factura(f_pdf)
        po = extraer_datos_pdf_oc(f_oc)
        
        # Lógica Fiscal Detracciones
        monto_det = 0.0
        pct_det = pf['PCT_DET']
        if (x['MONEDA'] == "PEN" and x['TOTAL'] > 700.00) or x['MONEDA'] == "USD":
            monto_det = x['TOTAL'] * (pct_det / 100)
        
        neto = x['TOTAL'] - monto_det

        # --- ARMADO DEL REPORTE HORIZONTAL ---
        data = {
            "Fecha Emisión": x['FECHA'],
            "RUC Proveedor": x['RUC_E'],
            "Razón Social": x['RAZON_SOCIAL'],
            "Comprobante": x['ID'],
            "Moneda": x['MONEDA'],
            "Base Imponible": x['BASE'],
            "IGV": x['IGV'],
            "Total Factura": x['TOTAL'],
            "% Detrac.": f"{pct_det}%",
            "Monto Detrac.": round(monto_det, 2),
            "Neto a Pagar": round(neto, 2),
            "Cód. Detrac.": pf['COD_DET'],
            "OC Referencia": pf['OC_REF'],
            "Cond. Pago (OC)": po['COND_PAGO'],
            "CECO": po['CECO'],
            "Situación OC": po['SITUACION']
        }

        df = pd.DataFrame([data])
        
        st.subheader("📋 Registro para Reporte")
        st.dataframe(df) # Tabla horizontal completa

        # Validaciones Visuales
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if po['SITUACION'] == "APROBADO":
                st.success(f"✅ ESTADO OC: {po['SITUACION']}")
            else:
                st.warning(f"⚠️ ESTADO OC: {po['SITUACION']}")
        
        with c2:
            if monto_det > 0:
                st.info(f"💡 Aplica Detracción: {x['MONEDA']} {monto_det:,.2f}")
            else:
                st.write("Factura libre de detracción.")
    else:
        st.error("Faltan archivos para completar el reporte.")
