from prometheus_client import Gauge, start_http_server
import os
import time

start_http_server(30124)
pod_cpu_used_nano_persec = Gauge("pod_cpu_used_nano_persec", "pod cpu used nanosec persec from command 'kubectl get podmetrics'", ['namespace', "pod"])

while True:
    namespaces = os.popen("kubectl get ns | awk '{print($1)}'")
    ns = namespaces.readline()
    ns = namespaces.readline().strip() # 直接下一个，跳过NAME行
    while ns != '':
        pods = os.popen("kubectl get podmetrics -n %s 2>&1 | awk '{print($1,$2)}'" % ns)
        pod = pods.readline()
        pod = pods.readline().strip() # 直接下一个，跳过NAME行
        while pod != '':
            pod = pod.split(' ')
            cpu_used = pod[1]
            if cpu_used != '0':
                cpu_used = cpu_used[:-1]
            pod_cpu_used_nano_persec.labels(namespace=ns, pod=pod[0]).set(cpu_used)
            pod = pods.readline().strip()

        pods.close()
        ns = namespaces.readline().strip()

    namespaces.close()
    time.sleep(15)
    

