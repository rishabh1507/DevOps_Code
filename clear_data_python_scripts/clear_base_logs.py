import os
import re
import subprocess
import smtplib
# from email.message import EmailMessage

error = dict()

def log_dict(temp_result3):
    d1 = dict()
    li = temp_result3
    for i in range(len(li)-2):
        temp_li = li[i].split(',')
        key1,val1 = temp_li[0],temp_li[1]
        if(key1 not in d1):
            d1[key1] = list()
            d1[key1].append(val1)
        else:
            d1[key1].append(val1) 
    return d1
 
def log_view(temp_result3):
    li = temp_result3.stdout.decode().split('\n')
    return li

def space_util():
    temp = subprocess.run('df -kh /base/logs',shell=True,stdout=subprocess.PIPE)
    print("Current space Util : \n", temp.stdout.decode())
    pass

def top_consumer():
    temp_result1 = subprocess.run('du -sh /base/logs/* | sort -hr | head -n 5',shell=True,stdout=subprocess.PIPE)
    print("Top 5 File Consumers are : \n", temp_result1.stdout.decode())
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

def inter_run():
    logs_temp = subprocess.run("find /base/logs/* -type f size +100M -ctime +5 -ctime -300 -print | xargs ls -lh | sort -k5,5 -h -r | awk {'print $3\",\"$9'}",shell=True,stdout=subprocess.PIPE)
    print(logs_temp.stdout.decode())
    all_logs = log_view(logs_temp)
    d2 = log_dict(all_logs)
    return d2

def delete_file(d2):
    for key1 in d2.keys():
        if(key1 == ""):
            continue
        else:
            cmd = "sudo -iu "+key1+"\n"
            for val in d2[key1]:
                cmd += "rm -r"+val+"\n"
            process1 = subprocess.run(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if(process1.stderr.decode()):
                error[key1]=process1.stderr.decode()
        print("files deleted")
    pass 



if __name__ == "__main__":
    space_util()
    top_consumer()
    temp_files = inter_run()
    print(temp_files)
    # delete_file(temp_files)
    # mail_dem()