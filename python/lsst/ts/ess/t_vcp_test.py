from vcp_ftdi import VCP_FTDI
p=VCP_FTDI('p','A601FT68',19200,1.5,'\r\n',85)
for i in range(10):
	print(p.readline().encode('utf-8'))
	