
report_txt

data = 'ArchivoText|ArchivoText|ArchivoText\nArchivoText|ArchivoText|ArchivoText'
model_id = env['report.txt.wiz'].create({
  'name': 'Reporte MDM',
  'txt_body': 'ArchivoTextÁndres|ArchivoText|ArchivoText\nArchivoText|ArchivoText|ArchivoText'
})
action = model_id.action_report_txt()


model_id = env['report.zip.wiz'].create({
  'name': 'Reporte ZIP',
})
# Reporte 1
dataReport1 = 'Nombre|Apellido Paterno|Apellido Materno|Edad|Direccion\nJuan Jose|Perez|Cruz|25|Col. Aurora'
model_id.action_create_report_data('reporte_uno.txt', dataReport1)
# Reporte 2
dataReport2 = 'id|Nombre Completo|RFC|CURP\n1|Juan Perez Cruz|XAXX010101000|XAXX010101000'
model_id.action_create_report_data('reporte_dos.txt', dataReport2)
action = model_id.action_report_zip()

1. Se crea el Wizard: "report.zip.wiz"

2. Se crea el contenido del reporte 1, en formato TXT
---- action_create_report_data.
---- Recibe el nombre del archivo txt, y el contenido


