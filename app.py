import streamlit as st
import xml.etree.ElementTree as ET
import pdfplumber
import re
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Control de Facturas - Voltan Group", layout="wide")

# --- FUNCIONES LÓGICAS ---
def normalizar_oc(texto):
    if not texto or "No" in str(texto): 
        return "No encontrado"
    # Extraer solo números y guiones
    limpio = re.sub(r'[^0-9-]', '', str(texto))
    if '-' in limpio:
        try:
            # Convierte 0001-0000499 en 1-499
            return "-".join([str(int(p)) for p in limpio.split('-') if p.isdigit()])
        except:
            return limpio
    return str(int(limpio)) if limpio.isdigit() else limpio

def extraer_datos_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto_completo += page.extract_text() or ""
            
            # 1. Buscar Orden de Compra (OC, Servicio, etc.)
            patron_oc = r"(?:ORDEN DE COMPRA|OC|O/C|SERVICIO)[:\s-]*(\d+(?:-\d+)?)"
            match_oc = re.search(patron_oc, texto_completo, re.IGNORECASE)
            oc_encontrada = match_oc.group(1) if match_oc else "No encontrado"
            
            # 2. Buscar Centro de Costo (CECO)
            patron_ceco = r"(?:CENTRO DE COSTO|CECO|C\. COSTO)[:\s-]*([A-Z0-9\s-]+)"
            match_ceco = re.search(patron_ceco, texto_completo, re.IGNORECASE)
            if match_ceco:
                # Limpiamos el texto para que no traiga saltos de línea
                ceco_encontrado = match_ceco.group(1).strip().split('\n')[0]
            else:
                ceco_encontrado = "No especificado"
            
            return {"oc": oc_encontrada, "ceco": ceco_encontrado}
    except Exception as e:
        return {"oc": "Error", "ceco": "Error"}

# --- INTERFAZ DE USUARIO ---
st.title("🛡️ Sistema de Validación Voltan Group")
st.write("Detección de Facturas, Órdenes de Compra y Centros de Costo")
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
                # --- PROCESAR XML (SUNAT) ---
                tree = ET.parse(f_xml)
                root = tree.getroot()
                ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
                
                prov = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns).text
                monto = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text
                
                # --- PROCESAR PDFs ---
                datos_f = extraer_datos_pdf(f_pdf)
                datos_o = extraer_datos_pdf(f_oc)
                
                v_oc_factura = normalizar_oc(datos_f['oc'])
                v_oc_documento = normalizar_oc(datos_o['oc'])
                
                # --- MOSTRAR RESULTADOS ---
                st.info(f"**Proveedor:** {prov} | **Monto:** S/ {monto}")
                
                # Validación de OC con semáforo
                if datos_f['oc'] == "No encontrado":
                    st.warning("⚠️ ESTADO: NO SE ENCONTRÓ REGISTRO DE OC EN LA FACTURA")
                elif v_oc_factura == v_oc_documento:
                    st.success(f"✅ ESTADO: COINCIDE TOTALMENTE (OC: {v_oc_factura})")
                    st.balloons()
                else:
                    st.error(f"❌ ESTADO: NO COINCIDE")
                    st.write(f"Factura dice: **{datos_f['oc']}** | OC dice: **{datos_o['oc']}**")

                # Mostrar Centro de Costo
                st.markdown(f"**Centro de Costo Detectado en OC:** `{datos_o['ceco']}`")
                
                # Tabla Resumen
                data_tabla = {
                    "Concepto": ["Número de OC", "Centro de Costo", "Monto Total"],
                    "En Factura PDF": [datos_f['oc'], "No aplica", f"S/ {monto}"],
                    "En Orden de Compra": [datos_o['oc'], datos_o['ceco'], "-"],
                    "Resultado": ["COINCIDE" if v_oc_factura == v_oc_documento else "REVISAR", "EXTRAÍDO", "OK"]
                }
                st.table(pd.DataFrame(data_tabla))
                
            except Exception as e:
                st.error(f"Error al procesar los archivos: {e}")
        else:
            st.error("Por favor, cargue los tres archivos (XML, PDF y OC).")
