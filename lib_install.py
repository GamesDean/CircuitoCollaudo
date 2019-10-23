import os
import sys
import time
#import yagmail

def lib_install(lib) :
    os.system("cd C:\Python27\Scripts")  
    os.system("pip install "+lib)


	
	
if __name__ == "__main__":
    lib_list =['pywin32','pyodbc','win32print','requests','zpl','Pillow','pylibdmtx','IPy','datetime','pyserial','yagmail','crcmod']
	
    for item in lib_list :
     lib_install(item)
     time.sleep(2)
	 
    #yag = yagmail.SMTP('lv.menowattge@gmail.com', 'menowattge')
    #yag.send('l.vulpio@menowattge.it', 'prova', 'collaudo effettuato')