# -*- coding: utf-8 -*-

import odoorpc

odoo = odoorpc.ODOO('localhost', port=8089)
odoo.login('odoo12_repNom', 'admin', 'admin')



user_data = odoo.execute('hr.payslip.run', 'dispersion_banorte_datas', [8])
print('----------- user_data ', user_data)



"""


H					| 01 - 01 - Tipo de Registro
NE 					| 02 - 02 - NE
77869 				| 05 - 05 - Numero de Emisora
20201230			| 06 - 08 - Fecha de Proceso
01					| 07 - 02 - Consecutivo
000010 				| 08 - 06 - No. total de registros
000000000001000 	| 09 - 15 - Importe Total de Registros Enviados
000000 				| 10 - 06 - No. Altas
000000000000000 	| 11 - 15 - Importe Total de Altas (13 Enterios, 2 Decimales)
000000 				| 12 - 06 - No Bajas
000000000000000 	| 13 - 15 - Importe Bajas
000000 				| 14 - 06 - No. Total Cuentas a verificar
0 					| 15 - 01 - Accion
0
0000000000002043875580000000000000000000000000000000000000000000000000000000


D
20201222
0000000002
000000000301899
014
40
014778605515738535
0

00000000                  

D 					| 01 - 01 - D
20201230			| 02 - 08 - Fecha Aplicacion
0000050428 			| 03 - 10 - No. Empleado
                                         			| 04 - 40 - Referencia del Servicio
                                         			| 05 - 40 - Referencia Leyenda del Ordenante
000000000000100 	| 06 - 15 - Importe
072 				| 07 - 03 - No. Banco Receptor
01 					| 08 - 02 - Tipo de Cuenta (01 - Cheques - 03 - Tarjeta de Debito - 40 - Clabe)
072180002128093188 	| 09 - 18 - Numero de Cuenta
0 					| 10 - 01 - Tipo de Movimiento
 					| 11 - 01 - Accion 
00000000 			| 12 - 08 - Importe IVA
                  	| 13 - 18 - Filler


D
20201222
0000000001                                                                                000000000819498127401272250011675462160 00000000                  


D202012300000050434                                                                                000000000000100 012 40 012180027599518570 0 00000000                  
D202012300000050610                                                                                000000000000100 002 40 002441700739887464 0 00000000                  
D202012300000050667                                                                                000000000000100 072 01 072180004583807276 0 00000000                  
D202012300000050697                                                                                000000000000100 014 40 014180570051634845 0 00000000                  
D202012300000050706                                                                                000000000000100 002 40 002180019760860978 0 00000000                  
D202012300000050729                                                                                000000000000100 072 01 072180003661719452 0 00000000                  
D202012300000050761                                                                                000000000000100 072 01 072180010329154504 0 00000000                  
D202012300000050783                                                                                000000000000100 012 40 012180029403688141 0 00000000                  
D202012300000050788                                                                                000000000000100 014 40 014180605821488345 0 00000000                  



"""