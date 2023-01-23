import os
import discord
from discord.ext import commands, tasks
import requests, json 
from requests.exceptions import HTTPError
import sqlite3
from dotenv import load_dotenv

con = sqlite3.connect('database.db')

# debug
#con.set_trace_callback(print)

cur = con.cursor()

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TWITCH_SECRET = os.getenv('TWITCH_SECRET')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
CHANNEL = os.getenv('CHANNEL')


if __name__ == '__main__':


    async def get_twitch_oauth():


        try:
            result = requests.post(f'https://id.twitch.tv/oauth2/token?client_id={TWITCH_CLIENT_ID}&client_secret={TWITCH_SECRET}&grant_type=client_credentials')
        except HTTPError as er:
            print(er)
        except Exception as er:
            print(er)
        
        
        client.TWITCH_OAUTH = result.json()['access_token']

        # for debug in case issue #1 is not resolved
        print(client.TWITCH_OAUTH)

    @tasks.loop(minutes=1)
    async def streamer_status():
        channel = client.get_channel(int(CHANNEL))
        url_builder = ''
        if len(client.TWITCH_OAUTH) > 0:
            headers = { 'Authorization': 'Bearer ' + client.TWITCH_OAUTH, 'Client-Id' : TWITCH_CLIENT_ID }

            cur.execute('SELECT name, id, is_live FROM streamers WHERE is_live = 0')
            streamer_list = cur.fetchall()
            if len(streamer_list) > 0:
                for streamer in streamer_list:
                    url_builder = url_builder + 'user_id=' + streamer[1] + '&'
                
                url_builder = 'https://api.twitch.tv/helix/streams?' + url_builder
                url_builder = url_builder[:len(url_builder)-1]

                try:
                    result = requests.get(url_builder, headers=headers)
                except HTTPError as er:
                    print(er)
                except Exception as er:
                    print(er)
                

                if result.status_code == 200:
                    result = result.json()
                    if len(result) > 0:

                        result = result['data']
                        for streamer in result:
                            cur.execute('UPDATE streamers SET is_live = 1 WHERE id = ?', (str(streamer['user_id']),))
                            con.commit()

                            await channel.send(f"{streamer['user_name']} is live at https://www.twitch.tv/{streamer['user_login']} playing {streamer['game_name']}")
                

            # check if streamers are still live
            # broken
            url_builder = ''
            cur.execute('SELECT name, id, is_live FROM streamers WHERE is_live = 1')
            streamer_list = cur.fetchall()

            if len(streamer_list) > 0:
                for streamer in streamer_list:
                    url_builder = url_builder + 'user_id=' + streamer[1] + '&'
                
                url_builder = 'https://api.twitch.tv/helix/streams?' + url_builder
                url_builder = url_builder[:len(url_builder)-1]


                try:
                    result = requests.get(url_builder, headers=headers)
                except HTTPError as er:
                    print(er)
                except Exception as er:
                    print(er)
                

                
                if result.status_code == 200:

                    result = result.json()

                    result = result['data']

                    for streamer in streamer_list:

                        all_vals = [value for elem in result for value in elem.values()]
                        if str(streamer[1]) not in all_vals:
                            cur.execute('UPDATE streamers SET is_live = 0 WHERE id = ?', (str(streamer[1]),))
                            con.commit()

                            await channel.send(f"{streamer[0]} went offline")


                





    @tasks.loop(minutes=45)
    async def check_oath():


        headers = { 'Authorization' : 'OAuth ' + client.TWITCH_OAUTH}

        
        try:
            result = requests.get(f'https://id.twitch.tv/oauth2/validate', headers=headers)
        except HTTPError as er:
            print(er)
        except Exception as er:
            print(er)

        if result.status_code != 200:
            await get_twitch_oauth()
            return True

        if int(result.json()['expires_in']) < 86400:
            await get_twitch_oauth()
        return True

    intents=discord.Intents.default()
    intents.message_content = True

    client=commands.Bot(intents=intents, command_prefix="!")
    client.TWITCH_OAUTH = ''

    @client.command()
    async def addstreamer(ctx, arg):

        channel = client.get_channel(int(CHANNEL))

        res = cur.execute("SELECT * FROM streamers WHERE name = ?", (arg,))
        name = res.fetchone()
        if name is not None:
            await channel.send("Streamer is already known")
            return

        
        if len(client.TWITCH_OAUTH) > 0:
            headers = { 'Authorization': 'Bearer ' + client.TWITCH_OAUTH, 'Client-Id' : TWITCH_CLIENT_ID }
            result = requests.get(f'https://api.twitch.tv/helix/users?login={arg}', headers=headers)
            if result.status_code == 200:
                cur.execute('INSERT INTO streamers (name, id, is_live) VALUES (?, ?, 0)', (result.json()['data'][0]['display_name'], result.json()['data'][0]['id']))
                con.commit()
                await channel.send(f'User {arg} added')


        else:
            await channel.send('bot is not ready')

    # function to remove streamer from database
    @client.command()
    async def removestreamer(ctx, arg):
            
            channel = client.get_channel(int(CHANNEL))
    
            res = cur.execute("SELECT * FROM streamers WHERE name = ?", (arg,))
            name = res.fetchone()
            if name is None:
                await channel.send("Streamer is not known")
                return
    
            cur.execute("DELETE FROM streamers WHERE name = ?", (arg,))
            con.commit()
            await channel.send(f"Streamer {arg} removed")

    @client.event
    async def on_ready():
        check_oath.start()
        streamer_status.start()
        

    @client.event
    async def on_message(message):
            await client.process_commands(message)

    client.run(DISCORD_TOKEN)