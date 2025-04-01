from scapy.all import *
import psutil
from collections import defaultdict
import os
from threading import Thread
import pandas as pd
import plotille

# get the all network adapter's MAC addresses
all_macs = {iface.mac for iface in ifaces.values()}
# A dictionary to map each connection to its correponding process ID (PID)
connection2pid = {}
# A dictionary to map each process ID (PID) to total Upload (0) and Download (1) traffic
pid2traffic = defaultdict(lambda: [0, 0])
# the global Pandas DataFrame that's used to track previous traffic stats
global_df = None
# global boolean for status of the program
is_program_running = True

global_graph_data = {}


def get_size(bytes):
    """
    Returns size of bytes in a nice format
    """
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < 1024:
            return f"{bytes:.2f}{unit}B"
        bytes /= 1024


def process_packet(packet):
    global pid2traffic
    try:
        # get the packet source & destination IP addresses and ports
        packet_connection = (packet.sport, packet.dport)
    except (AttributeError, IndexError):
        # sometimes the packet does not have TCP/UDP layers, we just ignore these packets
        pass
    else:
        # get the PID responsible for this connection from our `connection2pid` global dictionary
        packet_pid = connection2pid.get(packet_connection)
        if packet_pid:
            if packet.src in all_macs:
                # the source MAC address of the packet is our MAC address
                # so it's an outgoing packet, meaning it's upload
                pid2traffic[packet_pid][0] += len(packet)
            else:
                # incoming packet, download
                pid2traffic[packet_pid][1] += len(packet)


def get_connections():
    """A function that keeps listening for connections on this machine
    and adds them to `connection2pid` global variable"""
    global connection2pid
    while is_program_running:
        # using psutil, we can grab each connection's source and destination ports
        # and their process ID
        for c in psutil.net_connections():
            if c.laddr and c.raddr and c.pid:
                # if local address, remote address and PID are in the connection
                # add them to our global dictionary
                connection2pid[(c.laddr.port, c.raddr.port)] = c.pid
                connection2pid[(c.raddr.port, c.laddr.port)] = c.pid
        # sleep for a second, feel free to adjust this
        time.sleep(1)


def print_pid2traffic():
    global global_df
    # initialize the list of processes
    processes = []
    for pid, traffic in list(pid2traffic.items()):
        try:
            # `pid` is an integer that represents the process ID
            # `traffic` is a list of two values: total Upload and Download size in bytes
            try:
                # get the process object from psutil
                p = psutil.Process(pid)
                # get the name of the process, such as chrome.exe, etc.
                name = p.name()
            except psutil.NoSuchProcess:
                # if process is not found, simply continue to the next PID for now
                continue

            # get the time the process was spawned
            try:
                create_time = datetime.fromtimestamp(p.create_time())
            except OSError:
                # system processes, using boot time instead
                create_time = datetime.fromtimestamp(psutil.boot_time())
            # construct our dictionary that stores process info
            process = {
                "pid": pid,
                "name": name,
                # "create_time": create_time,
                "Upload": traffic[0],
                "Download": traffic[1],
            }
            try:
                # calculate the upload and download speeds by simply subtracting the old stats from the new stats
                process["Upload Speed"] = traffic[0] - global_df.at[pid, "Upload"]
                process["Download Speed  "] = traffic[1] - global_df.at[pid, "Download"]
            except (KeyError, AttributeError):
                # If it's the first time running this function, then the speed is the current traffic
                # You can think of it as if old traffic is 0
                process["Upload Speed"] = traffic[0]
                process["Download Speed  "] = traffic[1]
            # append the process to our processes list
            processes.append(process)

            if name not in global_graph_data:            
                global_graph_data[name] = [0] * 65
            data_speed = int( ((traffic[0] - global_df.at[pid, "Upload"]) + traffic[1] - global_df.at[pid, "Download"])/1024)
            global_graph_data[name].append(data_speed)
            if len(global_graph_data[name]) > 65:
                global_graph_data[name].pop(0)

        except Exception:
            continue
    # construct our Pandas DataFrame
    df = pd.DataFrame(processes)
    try:
        # set the PID as the index of the dataframe
        df = df.set_index("pid")
        # sort by column, feel free to edit this column
        df.sort_values("Download Speed  ", inplace=True, ascending=False)
    except KeyError as e:
        # when dataframe is empty
        pass
    # make another copy of the dataframe just for fancy printing
    printing_df = df.copy()
    printing_df = printing_df.head(10)

    try:
        # apply the function get_size to scale the stats like '532.6KB/s', etc.
        printing_df["Download"] = printing_df["Download"].apply(get_size)
        printing_df["Upload"] = printing_df["Upload"].apply(get_size)
        printing_df["Download Speed  "] = (
            printing_df["Download Speed  "].apply(get_size).apply(lambda s: f"{s}/s  ")
        )
        printing_df["Upload Speed"] = (
            printing_df["Upload Speed"].apply(get_size).apply(lambda s: f"{s}/s")
        )
    except KeyError as e:
        # when dataframe is empty again
        pass
    #clear the screen based on your OS

    if global_df is None:
        os.system("cls") if "nt" in os.name else os.system("clear")

    elif global_df.size != df.size:
        os.system("cls") if "nt" in os.name else os.system("clear")


    for i in range(40):
        print("\r\033[3A\033[3A")

    print("💎 \033[1mCrystalWire\033[0m ✨ 1.0 \033[3mhttp://github.com/rpfilomeno/crystalwire\033[0m\n")

    plot(df.head(3))
    stat(printing_df)
    # update the global df to our dataframe
    global_df = df


def stat(df: pd.DataFrame):


    lines = df.to_string().split("\n")
    n=0
    for line in lines:
        n+=1
        if n==3:
            print(f"\033[96m{line}\033[0m")
        elif n==4:
            print(f"\033[93m{line}\033[0m")
        elif n==5:
            print(f"\033[95m{line}\033[0m")
        else:
            print(line)



def plot(df: pd.DataFrame):
    colors = ["cyan","yellow","magenta"]
    fig = plotille.Figure()
    fig.width=70
    fig.height=6
    fig.origin=False
    fig.x_label="time"
    fig.y_label="total Kb/s"
    fig.set_x_limits(min_=0, max_=60)
    fig.set_y_limits(min_=0, max_=None)
    

    
    

    

    series = []
    for index, row in df.iterrows():
        series = global_graph_data[row['name']]
  
        n = []
        for i in range(0,len(series),1):
            n.append(i)
        fig.plot(X=n , Y=series, lc=colors[0])

        colors.pop(0)

    print(fig.show())




def print_stats():
    """Simple function that keeps printing the stats"""
    while is_program_running:
        time.sleep(1)
        print_pid2traffic()


if __name__ == "__main__":
    # start the printing thread
    printing_thread = Thread(target=print_stats)
    printing_thread.start()
    # start the get_connections() function to update the current connections of this machine
    connections_thread = Thread(target=get_connections)
    connections_thread.start()
    # start sniffing
    print("Started sniffing")
    sniff(prn=process_packet, store=False)
    # setting the global variable to False to exit the program
    is_program_running = False
