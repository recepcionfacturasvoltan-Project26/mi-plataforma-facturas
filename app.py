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
        # Unimos todo el texto y lo convertimos a mayúsculas para evitar errores de lectura
        texto = "".join([p.extract_text() or "" for p in pdf.pages]).upper()
        
        # 1. Buscar el mensaje legal de detracción
        mensaje_detraccion = "OPERACIÓN SUJETA AL SISTEMA DE PAGO DE OBLIGACIONES TRIBUTARIAS"
        tiene_mensaje = mensaje_detraccion in texto
        
        # 2. Buscar porcentaje (ejemplo: 12% o 12 %)
        match_pct = re.search(r"(\d{1,2})\s*%", texto)
        porcentaje = float(match_pct.group(1)) if match_pct else 0.0
        
        # 3. Buscar código de detracción (ej: 019, 037)
        match_cod = re.search(r"DETRACCI[ÓO]N[:\s-]*(\d{3})", texto)
        
        # 4. Buscar OC
        match_oc = re.search(r"(?:OC|ORDEN|SERVICIO)[:\s-]*(\d+(?:-\d+)?)", texto)
        
        return {
            "TIENE_MENSAJE": tiene_mensaje,
            "COD_DET": match_cod.group(1) if match_cod else "N/A",
            "PCT_DET": porcentaje,
            "OC_REF": match_oc.group(1) if match_oc else "No encontrado"
        }

def extraer_datos_pdf_oc(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "".join([p.extract_text() or "" for p in pdf.pages]).upper()
        match_pago = re.search(r"COND\.\s*PAGO[:\s-]*([A-Z0-9\s]+)", texto)
        match_situacion = re.search(r"SITUACI[ÓO]N\s*[:\s-]*([A-Z]+)", texto)
        match_ceco = re.search(r"(?:CECO|CENTRO COSTO)[:\s-]*([A-Z0-9-]+)", texto)
        
        return {
            "COND_PAGO": match_pago.group(1).strip() if match_pago else "NO ENCONTRADO",
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
        
        # --- LÓGICA FISCAL DE DETRACCIÓN ---
        monto_det = 0.0
        pct_aplicado = 0.0
        
        # Regla: Si tiene el mensaje O si es mayor a 700 PEN (o cualquier USD)
        if pf['TIENE_MENSAJE'] or (x['MONEDA'] == "PEN" and x['TOTAL'] > 700.00) or x['MONEDA'] == "USD":
            # Si detectó un porcentaje en el PDF lo usamos, si no, podrías poner uno por defecto (ej: 12)
            pct_aplicado = pf['PCT_DET'] if pf['PCT_DET'] > 0 else 0.0 
            monto_det = x['TOTAL'] * (pct_aplicado / 100)
        
        neto = x['TOTAL'] - monto_det

        # --- ARMADO DEL REPORTE HORIZONTAL ---
        data = {
            "Fecha": x['FECHA'],
            "Proveedor": x['RAZON_SOCIAL'],
            "RUC": x['RUC_E'],
            "Comprobante": x['ID'],
            "Moneda": x['MONEDA'],
            "Total Factura": x['TOTAL'],
            "Mensaje Detrac.": "SÍ" if pf['TIENE_MENSAJE'] else "NO",
            "% Detrac.": f"{pct_aplicado}%",
            "Importe Detrac.": round(monto_det, 2),
            "Neto a Pagar": round(neto, 2),
            "Cód. Detrac.": pf['COD_DET'],
            "OC Ref": pf['OC_REF'],
            "Cond. Pago": po['COND_PAGO'],
            "CECO": po['CECO'],
            "Situación OC": po['SITUACION']
        }

        df = pd.DataFrame([data])
        st.subheader("📋 Registro Horizontal")
        st.dataframe(df)

        # Validaciones de Alerta
        if x['TOTAL'] > 700 and not pf['TIENE_MENSAJE']:
            st.warning("⚠️ ALERTA: El monto supera los S/ 700 pero no se detectó el mensaje de detracción en el PDF.")
        
        if po['SITUACION'] == "APROBADO":
            st.success(f"✅ ORDEN DE COMPRA: {po['SITUACION']}")
        else:
            st.error(f"❌ SITUACIÓN OC: {po['SITUACION']}")
            
    else:
        st.error("Por favor cargue los 3 archivos.")
