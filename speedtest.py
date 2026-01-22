import speedtest


def check_internet_speed():
    st = speedtest
    print("Testing speed ....")
    download = st.download() / 1000000
    upload = st.upload() / 1000000

    st.get_best_server()
    ping = st.results.ping

    return {
        'download': round(download, 2),
        'upload': round(upload, 2),
        'ping': round(ping, 2)

    }


speed = check_internet_speed()
print(f'Download : {speed["download"]}  Mbps')
print(f'Upload : {speed["upload"]}  Mbps')
print(f'ping : {speed["ping"]}  Mbps')
