##
## meshchat "redux"
##
import sys
import os
import time
import re
import curses
from pubsub import pub
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
#from meshtastic.node import Node
#from meshtastic.util import message_to_json

connection_method = None
interface_mode = None
ip_regex = "^(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
serial_regex = r"\w+(/[\w.-]+)*"

# Determine which connection method / interface mode to use
if( len(sys.argv) < 2 ): # Display Helpful message about how to pass in a connection method
    print("Please provide a Serial Port or IP Address - example: python meshchat_redux.py 127.0.0.1  (or /path/to/serial-device)")
    exit()
else: # Determine if we were provided a serial port or ip address
    connection_method = sys.argv[1]
    if ( re.search(ip_regex, connection_method) ):
        interface_mode = "tcp"
        interface = TCPInterface(hostname=connection_method)
    elif ( re.search(serial_regex, connection_method) ):
        interface_mode = "serial"
        interface = SerialInterface(connection_method)
    else:
        print("Could not determine connection method by provided argument.")
        exit()

# @TODO Handle channel being passed on the cli?
channel_index = 0            # Replace with your channel index, usually 0
channel_list = []

# Determine backspace key code based on the platform / OS
if os.name == 'nt':  # For Windows
    BACKSPACE = 8
else:  # For Unix/Linux
    BACKSPACE = curses.KEY_BACKSPACE

# Parse Node Info
def parse_node_info(node_info):
    nodes = []
    for node_id, node in node_info.items():
        nodes.append({
            'num': node_id,
            'user': {
                'shortName': node.get('user', {}).get('shortName', 'Unknown')
            }
        })
    return nodes

# Parce Channel Info
def parse_channel_info(local_node):
    for c in local_node.channels:
        if c.role != 0: # 0 = DISABLED
            channel_list.append(c.index)
    return channel_list

# Display Loading Screen
def show_loading_screen(stdscr, interface_mode):
    stdscr.clear()
    stdscr.refresh()

    # Calculate center position for "Fetching node list from radio..." text
    height, width = stdscr.getmaxyx()
    text = f"Fetching node list from radio via {interface_mode} interface..."
    x = width // 2 - len(text) // 2
    y = height // 2

    stdscr.addstr(y, x, text, curses.A_BOLD)
    stdscr.refresh()
    time.sleep(2.5)

# Display Help
def display_help(stdscr):
    # Clear the screen
    stdscr.clear()

    # Display help message
    help_message = [
        "=== Help ===",
        "",
        "Commands:",
        "/h - Display this help message",
        "/ln - Display the list of nodes",
        "/lc - Display the list of Channels",
        "/sc <#> - Switch to Channel Number <#>",
        "/m !nodeId <message> - Send a private message to nodeId",
        "/cs - Clear Screen / Message History",
        "/q or Ctrl-C - Quit",
        "",
        "(Press any key to return to chat)"
    ]

    # Calculate position to display help message above the horizontal line
    help_start_y = curses.LINES - len(help_message) - 7  # Adjust for padding and horizontal line

    for idx, line in enumerate(help_message):
        stdscr.addstr(help_start_y + idx, 2, line)

    # Insert a solid horizontal line with padding
    stdscr.hline(curses.LINES - 3, 2, curses.ACS_HLINE, curses.COLS - 4)  # 2 spaces padding on each side

    stdscr.refresh()
    stdscr.getch()  # Wait for key press

# Handle incoming Packets
def on_receive(packet, interface, node_list, stdscr, input_text, message_lines):
    try:

        ## DEBUG
        #str_packet = str(packet)
        #print(f"DEBUG: Receieved Packet. {str_packet}")
            
        if 'decoded' in packet and packet['decoded'].get('portnum') == 'TEXT_MESSAGE_APP':
        #if 'decoded' in packet:
            message = packet['decoded']['payload'].decode('utf-8')
            fromnum = packet['fromId']
            shortname = next((node['user']['shortName'] for node in node_list if node['num'] == fromnum), 'Unknown')
            timestamp = time.strftime("%H:%M:%S")

            # Determine if it's a private message (toId is not ^all)
            is_private_message = packet['toId'] != '^all'

            # Split message into lines
            lines = message.splitlines()

            # Push existing messages up
            while len(message_lines) + len(lines) >= curses.LINES - 5:  # -5 to leave space for the horizontal line, input line, and padding
                message_lines.pop(0)

            # Add each line of the message with timestamp
            for line in lines:
                if is_private_message:
                    dest_shortname = next((node['user']['shortName'] for node in node_list if node['num'] == packet['toId']), 'Unknown')
                    formatted_msg = f"{timestamp} {shortname} to {packet['toId']} ({dest_shortname}) 📩 {line}"
                    message_lines.append((formatted_msg, True))  # Store as tuple with PM flag
                else:
                    formatted_msg = f"{timestamp} {shortname}: {line}"
                    message_lines.append((formatted_msg, False))  # Store as tuple with PM flag

            # Clear the screen
            stdscr.clear()

            # Print message lines with padding
            for idx, (msg, is_pm) in enumerate(message_lines[::-1]):  # Print from bottom to top
                if is_pm:
                    stdscr.addstr(curses.LINES - 4 - idx, 2, msg, curses.color_pair(2) | curses.A_BOLD)  # 2 spaces padding and 1 line of padding
                else:
                    stdscr.addstr(curses.LINES - 4 - idx, 2, msg)  # 2 spaces padding and 1 line of padding

            # Insert a solid horizontal line with padding
            stdscr.hline(curses.LINES - 3, 2, curses.ACS_HLINE, curses.COLS - 4)  # 2 spaces padding on each side

            # Set the input line with padding
            stdscr.addstr(curses.LINES - 2, 2, f"{prompt_text} {input_text} ")
            stdscr.move(curses.LINES - 2, 2 + len(prompt_text) + len(input_text) + 1)

            # Refresh the screen
            stdscr.refresh()

    except KeyError:
        # Ignore KeyError for packets without 'decoded' key or 'channel' key
        pass
    except UnicodeDecodeError as e:
        print(f"UnicodeDecodeError: {e}")

# Display nodes
def list_nodes(node_list, message_lines):
    message_lines.append(("", False))
    message_lines.append(("Nodes:", False))
    for idx, node in enumerate(node_list[::-1]):  # Print from bottom to top
        formatted_msg = f" {node['num']}: {node['user']['shortName']}"
        message_lines.append((formatted_msg, False))

    # Push existing messages up
    while len(message_lines) >= curses.LINES - 5:
        message_lines.pop(0)

# Display Channels
def list_channels(local_node, message_lines):
    message_lines.append(("", False))
    message_lines.append(("Channels:", False))
    for c in local_node.channels:
        #cStr = message_to_json(c.settings)
        # don't show disabled channels
        if c.role != 0: # 0 = DISABLED
            message_lines.append((f" {c.index}", False))

def change_channel(channel_index, new_channel_id, message_lines):
    # Double-check that channel is in list
    if (new_channel_id in channel_list):
        message_lines.append((f"Switching from channel {channel_index} to channel {new_channel_id}", False))
        channel_index = new_channel_id
        # @TODO Actually switch channels
    else:
        message_lines.append(("Invalid Channel Selected", False))

def main(stdscr):

    running = True # Used to more gracefully exit our while loop
    showcounter = 0
    input_text = ""
    message_lines = []
    suggestions = []
    display_suggestions = False
    local_node = None

    try:

        # Our local node
        local_node = interface.getNode('^local') # Node(interface, interface.localNode.nodeNum)

        # Retrieve and parse node information
        node_list = parse_node_info(interface.nodes)

        # Channel Info
        channel_list = parse_channel_info(local_node)

        # Initialize curses settings
        curses.curs_set(1)  # Show cursor
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Default color
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Yellow for PMs

        # Enable echo mode explicitly
        curses.echo()

        # Show loading screen while retrieving node information
        show_loading_screen(stdscr, interface_mode)

        # Use the local node's short name as the prompt if available
        global prompt_text

        if node_list:
            prompt_text = f"{node_list[0]['user']['shortName']}@{connection_method}>" # Adjust prompt formatting here
        else:
            prompt_text = f"Unknown@{connection_method}>" # Fallback if node list is empty

        # Clear loading screen and refresh
        stdscr.clear()
        stdscr.refresh()

        # Insert a solid horizontal line with padding
        stdscr.hline(curses.LINES - 3, 2, curses.ACS_HLINE, curses.COLS - 4)  # 2 spaces padding on each side

        # Set the input line prompt with padding
        stdscr.addstr(curses.LINES - 2, 2, f"{prompt_text} {input_text} ")
        stdscr.move(curses.LINES - 2, 2 + len(prompt_text) + len(input_text) + 1)
        stdscr.refresh()

        # Subscribe the callback function to message reception
        def on_receive_wrapper(packet, interface):
            on_receive(packet, interface, node_list, stdscr, input_text, message_lines)

        pub.subscribe(on_receive_wrapper, "meshtastic.receive")

        # Main loop for user interaction
        while running:
            key = stdscr.getch()
            if key != curses.ERR:
                if key in (curses.KEY_BACKSPACE, 127, 8):  # Check for backspace, delete, and Ctrl+H
                    if len(input_text) > 0:
                        # Delete character from input_text
                        input_text = input_text[:-1]
                        display_suggestions = False

                elif key == curses.KEY_ENTER or key == 10 or key == 13:

                    if (input_text.strip() == '/lc'): # lc = List Channels
                        list_channels(local_node, message_lines)
                        input_text = ""
                    elif (input_text.strip().startswith('/sc ')): # sc = Switch Channel
                        command_parts = input_text.strip().split(maxsplit=1)
                        if (len(command_parts) == 2):
                            new_channel_id = int(command_parts[1])
                            change_channel(channel_index, new_channel_id, message_lines)
                        else:
                            message_lines.append(("Invalid command format. Use '/sc <Channel Number>'", False))
                        input_text = ""
                    elif (input_text.strip() == '/ln'): # ln = List Nodes
                        list_nodes(node_list, message_lines)
                        # Clear the input line
                        input_text = ""

                    elif (input_text.strip().startswith('/m !')): # m = (Direct) Message
                        # Extract nodeId and message from input
                        command_parts = input_text.strip().split(maxsplit=2)
                        if len(command_parts) >= 3:
                            nodeId = command_parts[1]
                            message = command_parts[2]
                            # Send private message
                            interface.sendText(message, nodeId, channelIndex=channel_index)
                            # Display own message immediately
                            timestamp = time.strftime("%H:%M:%S")
                            dest_shortname = next((node['user']['shortName'] for node in node_list if node['num'] == nodeId), 'Unknown')
                            message_lines.append((f"{timestamp} {prompt_text} to {nodeId} ({dest_shortname}) 📩 {message}", True))  # Store as tuple with PM flag
                            input_text = ""
                            stdscr.clear()
                        else:
                            message_lines.append(("Invalid command format. Use '/m !nodeId <message>'", False))

                    elif (input_text.strip() == '/h'):
                        # Show help screen
                        display_help(stdscr)
                        input_text = ""

                    elif (input_text.strip() == '/cs'): # cs = Clear Screen
                        message_lines = []
                        input_text = ""
                        stdscr.clear()

                    elif (input_text.strip() == '/q'): # q = Quit
                        stdscr.clear()
                        running = False # Break While Loop

                    elif (input_text.strip().startswith('/')):
                        message_lines.append(("Invalid command format. Use '/h for Command Help'", False))

                    elif (len(input_text.strip()) == 0):
                        input_text = ""
                        # Silently do not send public empty messages

                    else:
                        # Send public message
                        interface.sendText(input_text, channelIndex=channel_index)
                        # Display own message immediately
                        timestamp = time.strftime("%H:%M:%S")
                        message_lines.append((f"{timestamp} {prompt_text} {input_text}", False))
                        input_text = ""

                    # Push existing messages up
                    while len(message_lines) >= curses.LINES - 5:
                        message_lines.pop(0)

                    display_suggestions = False  # Reset suggestions after sending a message

                elif key == curses.KEY_UP:
                    if showcounter == 0:
                        showcounter = len(message_lines)
                    if showcounter > 1:
                        showcounter -= 1

                elif key == curses.KEY_DOWN:
                    if showcounter < len(message_lines) - 1:
                        showcounter += 1

                else:
                    input_text += chr(key)
                    display_suggestions = True  # Show suggestions on input

                # Clear the screen
                stdscr.clear()

                # Display message lines
                for idx, (msg, is_pm) in enumerate(message_lines[-showcounter:][::-1]):  # Print from bottom to top
                    if is_pm:
                        stdscr.addstr(curses.LINES - 4 - idx, 2, msg, curses.color_pair(2) | curses.A_BOLD)  # 2 spaces padding and 1 line of padding
                    else:
                        stdscr.addstr(curses.LINES - 4 - idx, 2, msg)  # 2 spaces padding and 1 line of padding

                # Insert a solid horizontal line with padding
                stdscr.hline(curses.LINES - 3, 2, curses.ACS_HLINE, curses.COLS - 4)  # 2 spaces padding on each side

                # Set the input line with padding
                stdscr.addstr(curses.LINES - 2, 2, f"{prompt_text} {input_text} ")
                stdscr.move(curses.LINES - 2, 2 + len(prompt_text) + len(input_text) + 1)

                # Display suggestions if applicable
                if display_suggestions:
                    # Add code to display suggestions based on input_text
                    # @TODO - tab-complete?
                    pass

                stdscr.refresh()

    except KeyboardInterrupt:
        pass
    finally:
        # Ensure the interface is closed on exit
        if interface is not None:
            interface.close()

if __name__ == "__main__":
    curses.wrapper(main)