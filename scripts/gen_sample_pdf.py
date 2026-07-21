"""Genera un PDF mínimo con texto embebido para tests unitarios."""
import sys
sys.path.insert(0, r"C:\Users\javier.salas.blanco\Projects\hackathon-draft\backend")

from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.cell(0, 10, text="Términos y condiciones del contrato de alquiler.", new_x="LMARGIN", new_y="NEXT", align="L")
pdf.cell(0, 10, text="Cláusula primera: El plazo del contrato será de 24 meses.", new_x="LMARGIN", new_y="NEXT", align="L")
pdf.ln(5)
pdf.cell(0, 10, text="Cláusula segunda: El precio mensual se actualizará por Índice IPC.", new_x="LMARGIN", new_y="NEXT", align="L")

output_path = r"C:\Users\javier.salas.blanco\Projects\hackathon-draft\backend\ingestion\tests\fixtures\sample_text.pdf"
pdf.output(output_path)
print(f"PDF generado: {output_path}")
print(f"Tamaño: {__import__('os').path.getsize(output_path)} bytes")
