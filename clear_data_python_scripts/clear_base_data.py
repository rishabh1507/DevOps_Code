import os
import re
import subprocess
import smtplib
from email.message import EmailMessage


error = dict()

def list_view(temp_st):
    li = temp_st.stdout.decode().split('\n')
    return li

def space_util():
    temp = subprocess.run('df -kh /base/data',shell=True,stdout=subprocess.PIPE)
    print("Current space Util : \n", temp.stdout.decode())

def top_consumer():
    temp_result1 = subprocess.run('du -sh /base/data/* | sort -hr | head -n 5',shell=True,stdout=subprocess.PIPE)
    print("Top 5 File Consumers are : \n", temp_result1.stdout.decode())


def inter_run():
    top_con = subprocess.run("du -sh /base/data/* | sort -hr | head -n 1 | awk {'print $2'}",shell=True,stdout=subprocess.PIPE)
    print(top_con.stdout.decode())
    list_top_con = list_view(top_con)
    print(list_top_con)
    for i in range(len(list_top_con)-1):
        owner  = subprocess.run("ls -l "+list_top_con[i]+" | sed -n '1!p' | head -n 1 |awk {'print $3'}",shell=True,stdout=subprocess.PIPE)
        spec_log = subprocess.run("ls "+list_top_con[i]+" | sort -hr | head -n 1 | sed 's/[0-9,.]//g'",shell=True,stdout=subprocess.PIPE)
        print(spec_log.stdout.decode())
        curr_ver_temp = subprocess.run("find /base/apps/web -name "+spec_log.stdout.decode().strip()+"*.war | sort -nr | head -n 1 | sed 's/[A-Z a-z / ]//g' ",shell=True,stdout=subprocess.PIPE)
        curr_ver = curr_ver_temp.stdout.decode().split("--") 
        curr_ver = curr_ver[1]
        curr_ver = curr_ver[:len(curr_ver)-2]
        curr_ver = '1.99'
        all_ver = subprocess.run("ls "+list_top_con[i]+" | sed 's/[A-Z a-z -]//g'",shell=True,stdout=subprocess.PIPE)
        list_all_ver = list_view(all_ver)
        delete_data(list_top_con[i],spec_log.stdout.decode(),curr_ver,list_all_ver,owner.stdout.decode())
    pass

def delete_data(top_con1,spec_log1,curr_ver1,list_all_ver1,owner):
    print(top_con1,spec_log1,curr_ver1,list_all_ver1,owner)
    cmd = "sudo +iu "+owner+" \n "
    for i in range(len(list_all_ver1)-1):
        if(float(list_all_ver1[i])<float(curr_ver1)):
            cmd = cmd +'sudo rm -r '+top_con1+"/"+spec_log1.strip()+""+list_all_ver1[i]+" \n "
    ip = input("Are you sure you want to delete above listed files ? (y/n)")
    if(ip=="y"):
        print(cmd)
        #process1 = subprocess.run(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if(process1.stderr.decode()):
            error[owner]=process1.stderr.decode()                    
        print("deleted the files\n")   
    else:
        print("process terminated")
    pass

def mail_dem(error):
    if(len(error)==0):
        print("No Error during deleting process")
        return
    else:
        mail_body=""
        for i,j in error.items():
            mail_body = mail_body +i+": "+j
             
        msg = EmailMessage()
        EMAIL_ADDRESS = "email"
        EMAIL_PASSWORD = "pass"
        msg = EmailMessage()
        msg['Subject'] = 'Error /base/data'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg.set_content(mail_body)
    
        with smtplib.SMTP_SSL('smtp.gmail.com',465) as smtp:
            smtp.login(EMAIL_ADDRESS,EMAIL_PASSWORD)
            smtp.send_message(msg)
    
        print("mail sent") 
    pass


if __name__ == "__main__":
    space_util()
    top_consumer()
    inter_run()
    mail_dem()