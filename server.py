import os
import pickle
from socket import *
from time import sleep
from server_utils import *
from file_writer import *


def receive_number_of_packets():
    while True:
        try:
            num = int(receive_message(server_socket).decode())
            # acknowledges that the number of packets info has arrived and is valid
            send_acknowledge(server_socket, client_address)
            return num
        except ValueError:
            # acknowledges that the number of packets info is not valid
            send_not_acknowledge(server_socket, client_address)


def send_number_of_packets(number):
    num = "%s" % number
    while True:
        try:
            server_socket.sendto(num.encode(), client_address)
            rps = server_socket.recv(BUFFER_SIZE)
            if rps.decode() == 'ACK':
                break
        except error:
            pass


def receive_file(fn, num):
    packets = []
    # tries to collect packets until the number of collected packets is equal to the original number of packets
    while True:
        failed_attempts = 0
        print(num)
        for i in range(num):
            data = server_socket.recv(BUFFER_SIZE)
            content = pickle.loads(data)
            packets.append(content)
            print('Received packet %s' % content['pos'])
        # re-orders the list based on the initial position of the packets
        packets.sort(key=lambda x: x['pos'])
        # if all packets have arrived, then the server notifies the client and proceeds to write onto the new file
        if packets.__len__() == num:
            send_acknowledge(server_socket, client_address)
            break
        else:
            failed_attempts += 1
            if failed_attempts < MAX_FAILED_ATTEMPTS:
                packets.clear()
                send_retry_acknowledge(server_socket, client_address)
            else:
                send_not_acknowledge(server_socket, client_address)
    # writes gathered data onto the new file of name 'fn'
    write_on_file(fn, packets)


def create_packet_list(file_path):
    with open(file_path, 'rb') as file_io:
        # calculates the number of packets using the size of both the file and the buffer (considering packets' headers)
        num_of_packages = file_io.read().__len__() // UPLOAD_SIZE + 1
        packet_list = []
        for i in range(num_of_packages):
            msg = file_io.read(UPLOAD_SIZE)
            # each packet consists of a position and some data read from the file
            packet_list.append({'pos': i, 'data': msg})
        return packet_list


def send_packets(packet_list):
    # each packet must be sent to the client
    for packet in packet_list:
        server_socket.sendto(pickle.dumps(packet), client_address)
        sleep(0.1)


def send_file(file_path):
    # creates a list of packets by reading the file to send
    packet_list = create_packet_list(file_path)
    send_number_of_packets(packet_list.__len__())
    send_packets(packet_list)
    # waits for the acknowledgment
    while True:
        try:
            # gets the response of the client upon the arrival of the packets
            rps = receive_message(server_socket)
            if rps.decode() == 'ACK':
                # this operation has been successful, therefore it is over
                break
            elif rps.decode() == 'RETRY':
                # this operation has not been successful, the client asks the server to retry
                send_packets(packet_list)
            elif rps.decode() == 'NACK':
                # this operation has not been successful, the client concludes that the operation is definitively over
                print('File transfer failed')
                break
        except error:
            # timeout error on the arrival of the acknowledgment, the server retries to obtain it
            pass


server_socket = socket(AF_INET, SOCK_DGRAM)
server_socket.bind(('', SERVER_PORT))
server_socket.settimeout(None)
file_prefix = os.getcwd() + "\\serverFiles\\"
print("The server is ready to receive.")

while True:
    try:
        server_socket.settimeout(None)
        command, client_address = server_socket.recvfrom(BUFFER_SIZE)
        match command.decode():
            case 'list':
                server_socket.sendto(os.listdir(file_prefix).__str__().encode(), client_address)
            case 'get':
                # the server has to send the file and wait for acknowledgment from the client
                server_socket.settimeout(TIMEOUT)
                file_name = server_socket.recv(BUFFER_SIZE).decode()
                # the server has to notify the client on the presence of the requested file among the server files
                if os.listdir(file_prefix).__contains__(file_name):
                    send_message(server_socket, client_address, 'ACK')
                else:
                    send_message(server_socket, client_address, 'NACK')
            case 'put':
                # the server has to collect the packets sent by the client and acknowledge the latter on the completion
                server_socket.settimeout(None)
                file_name = receive_message(server_socket).decode()
                receive_file(file_prefix + file_name, receive_number_of_packets())
            case 'quit':
                server_socket.close()
    except error:
        pass
