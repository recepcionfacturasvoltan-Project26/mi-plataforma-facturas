import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Gestión Contable - Voltan Group", layout="wide")

# --- FUNCIONES DE APOYO ---
def normalizar_oc(texto):
    if not texto or "No" in str(texto): return "No encontrado"
    limpio = re.sub(r'[^0-9-]', '', str(texto))
    if '-' in limpio:
        try: return "-".join([str(int(p)) for p in limpio.split('-') if p.isdigit()])
        except: return limpio
    return str(int(limpio)) if limpio.isdigit() else limpio

def extraer_datos_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            texto_completo = ""
            primera_descripcion = "No encontrada"
            for i, page in enumerate(pdf.pages):
                texto_pag = page.extract_text() or ""
                texto_completo += texto_pag
                # Extraer descripción (basado en una posición común o palabra clave)
                if i == 0:
                    lineas = texto_pag.split('\n')
                    for linea in lineas:
                        if any(k in linea.upper() for k in ["DESC", "CANT", "SERV"]):
                            # Intentamos agarrar la línea siguiente a la cabecera
                            idx = lineas.index(linea)
                            if idx + 1 < len(lineas):
                                primera_descripcion = lineas[idx+1][:60] # Primeros 60 caracteres
                                break

            # Buscar OC y CECO
            patron_oc = r"(?:ORDEN DE COMPRA|OC|O/C|SERVICIO)[:\s-]*(\d+(?:-\d+)?)"
            match_oc = re.search(patron_oc, texto_completo, re.IGNORECASE)
            
            patron_ceco = r"(?:CENTRO DE COSTO|CECO|C\. COSTO)[:\s-]*([A-Z0-9\s-]+)"
            match_ceco = re.search(patron_ceco, texto_completo, re.IGNORECASE)
            
            # Buscar Detracción (Porcentaje y Código)
            patron_cod_det = r"(?:CÓDIGO|COD|COD\.)\s*(?:DE)?\s*DETRACCI[ÓO]N[:\s-]*(\d{3})"
            match_cod = re.search(patron_cod_det, texto_completo, re.IGNORECASE)
            
            patron_pct_det = r"(\d{1,2})\s*%\s*(?:DE)?\s*DETRACCI[ÓO]N"
            match_pct = re.search(patron_pct_det, texto_completo, re.IGNORECASE)

            return {
                "oc": match_oc.group(1) if match_oc else "No encontrado",
                "ceco": match_ceco.group(1).strip().split('\n')[0] if match_ceco else "No especificado",
                "desc": primera_descripcion,
                "cod_det": match_cod.group(1) if match_cod else "N/A",
                "pct_det": float(match_pct.group(1)) if match_pct else 0.0
            }
    except:
        return {"oc": "Error", "ceco": "Error", "desc": "Error", "cod_det": "N/A", "pct_det": 0.0}

# --- INTERFAZ ---
st.title("🛡️ Plataforma Contable Voltan Group")
st.markdown("---")

f_xml = st.file_uploader("1. XML Factura", type=["xml"])
f_pdf = st.file_uploader("2. PDF Factura", type=["pdf"])
f_oc = st.file_uploader("3. PDF Orden de Compra", type=["pdf"])

if st.button("🚀 PROCESAR Y CALCULAR"):
    if f_xml and f_pdf and f_oc:
        # Procesar XML
        tree = ET.parse(f_xml)
        root = tree.getroot()
        ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
              'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
        
        prov = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns).text
        monto_total = float(root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text)
        moneda_raw = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).attrib.get('currencyID')
        # Cambiar símbolos por USD o PEN
        moneda = "PEN" if moneda_raw == "PEN" else "USD" if moneda_raw == "USD" else moneda_raw

        # Procesar PDFs
        d_f = extraer_datos_pdf(f_pdf)
        d_o = extraer_datos_pdf(f_oc)
        
        # Cálculos de Detracción
        monto_detraccion = monto_total * (d_f['pct_det'] / 100)
        cuota_pago = monto_total - monto_detraccion

        # --- MOSTRAR RESULTADOS ---
        st.subheader(f"Resumen para: {prov}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Monto Total", f"{moneda} {monto_total:,.2f}")
        c2.metric("Detracción (%)", f"{d_f['pct_det']}%")
        c3.metric("Importe Detracción", f"{moneda} {monto_detraccion:,.2f}")
        c4.metric("Valor Cuota (Neto)", f"{moneda} {cuota_pago:,.2f}", delta_color="normal")

        st.markdown("---")
        
        # Tabla Detallada
        data_final = {
            "Campo": ["Descripción Producto/Servicio", "Código Detracción", "Centro de Costo (CECO)", "Orden de Compra"],
            "Información Extraída": [d_f['desc'], d_f['cod_det'], d_o['ceco'], d_f['oc']],
            "Estado": ["OK", "Validar" if d_f['cod_det'] == "N/A" else "Detectado", "Extraído", 
                        "COINCIDE" if normalizar_oc(d_f['oc']) == normalizar_oc(d_o['oc
