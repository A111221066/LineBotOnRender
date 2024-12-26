from flask import Flask
app = Flask(__name__)

from flask import request, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from linebot import  LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent,  LocationSendMessage, TemplateSendMessage, ButtonsTemplate, URITemplateAction, ConfirmTemplate, PostbackTemplateAction
from urllib.parse import parse_qsl
from sqlalchemy import text

# 定義 LINE Bot Channel Secret 及 Access Token
import os

line_bot_api = LineBotApi(os.environ.get('Channel_Access_Token'))
handler = WebhookHandler(os.environ.get('Channel_Secret'))
   

# 定義 PostgreSQL 連線字串
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://admin:123456@127.0.0.1:5432/restaurant'
db = SQLAlchemy(app)
# 定義 LIFF ID
liffid = '2006726478-LA91yJwV'

#LIFF靜態頁面
@app.route('/page')
def page():
	return render_template('hotel_form.html', liffid = liffid)
	
# 重置資料庫
@app.route('/createdb')
def createdb():
    sql = """
    DROP TABLE IF EXISTS hoteluser, booking;
    
    CREATE TABLE hoteluser (
    id serial NOT NULL,
    uid character varying(50) NOT NULL,
    PRIMARY KEY (id));

    CREATE TABLE booking (
    id serial NOT NULL,
    bid character varying(50) NOT NULL,
    roomamount character varying(5) NOT NULL,
    datein character varying(20) NOT NULL,
    timein character varying(20) NOT NULL,
    PRIMARY KEY (id))
    """
    db.session.execute(text(sql))
    db.session.commit()  
    return "資料表建立成功！"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    sql_cmd = "select * from hoteluser where uid='" + user_id + "'"
    query_data = db.session.execute(text(sql_cmd)).fetchall()
    if len(list(query_data)) == 0:
        sql_cmd = "insert into hoteluser (uid) values('" + user_id + "');"
        db.session.execute(text(sql_cmd))
        db.session.commit()

    mtext = event.message.text
    
    if mtext == '@預訂用餐':
        sendBooking(event, user_id)

    elif mtext == '@取消預訂':
        sendCancel(event, user_id)

    elif mtext == '@想食天堂顧客滿意度調查表':
        sendAbout(event)

    elif mtext == '@位置資訊':
        sendPosition(event)

    elif mtext == '@真人服務':
        sendContact(event)

    elif mtext[:3] == '###' and len(mtext) > 3:  #處理LIFF傳回的FORM資料
         manageForm(event, mtext, user_id)

    elif mtext[:6] == '123456' and len(mtext) > 6:  #推播給所有顧客
         pushMessage(event, mtext)

@handler.add(PostbackEvent)  #PostbackTemplateAction觸發此事件
def handle_postback(event):
    backdata = dict(parse_qsl(event.postback.data))  #取得Postback資料
    if backdata.get('action') == 'yes':
        sendYes(event, event.source.user_id)
    else:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='你已放棄取消訂位操作！'))

def sendBooking(event, user_id):  #預約用餐
    try:
        sql_cmd = "select * from booking where bid='" + user_id + "'"
        query_data = db.session.execute(text(sql_cmd)).fetchall()
        if len(list(query_data)) == 0:
            message = TemplateSendMessage(
                alt_text = "預訂用餐",
                template = ButtonsTemplate(
                    thumbnail_image_url='https://imgur.com/4BP2RNz.jpg',
                    title='預訂用餐',
                    text='您目前沒有預訂用餐，可以開始訂位。',
                    actions=[
                        URITemplateAction(label='預訂用餐', uri='https://liff.line.me/' + liffid)  #開啟LIFF讓使用者輸入訂房資料
                    ]
                )
            )
        else:  #已有訂位記錄
            message = TextSendMessage(
                text = '您目前已有訂位記錄，不能再訂位。'
            )
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))

def sendCancel(event, user_id):  #取消訂位
    try:
        sql_cmd = "select * from booking where bid='" + user_id + "'"
        query_data = db.session.execute(text(sql_cmd)).fetchall()
        bookingdata = list(query_data)
        if len(bookingdata) > 0:
            amount = bookingdata[0][2]
            in_date = bookingdata[0][3]
            in_time = bookingdata[0][4]
            text1 = "您的預訂用餐資料如下："
            text1 += "\n人數：" + amount
            text1 += "\n用餐日期：" + in_date
            text1 += "\n用餐時間：" + in_time
            message = [
                TextSendMessage(  #顯示預訂資料
                    text = text1
                ),
                TemplateSendMessage(  #顯示確認視窗
                    alt_text='取消訂位確認',
                    template=ConfirmTemplate(
                        text='你確定要取消訂位嗎？',
                        actions=[
                            PostbackTemplateAction(  #按鈕選項
                                label='是',
                                data='action=yes'
                            ),
                            PostbackTemplateAction(
                                label='否',
                                data='action=no'
                           )
                        ]
                    )
                )
            ]
        else:  #沒有訂位記錄
            message = TextSendMessage(
                text = '您目前沒有訂位記錄！'
            )
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))
        
def sendAbout(event):  # 想食天堂顧客滿意度調查表
    try:
        text1 = '''我們非常重視您的用餐體驗，請您花幾分鐘填寫以下滿意度調查表，幫助我們提供更好的服務！您的意見對我們非常重要！
        
1. 您對菜品的品質和口味滿意嗎？
2. 您對服務人員的態度滿意嗎？
3. 您對餐廳整體環境的滿意度如何？
4. 您對餐廳的價位是否滿意？

謝謝您的寶貴意見！'''

        message = TemplateSendMessage(
            alt_text='顧客滿意度調查表',
            template=ButtonsTemplate(
                title='想食天堂 顧客滿意度調查',
                text=text1,
                actions=[
                    URITemplateAction(
                        label='開始填寫調查表',
                        uri='https://forms.gle/wD9fkz1dVR1zGHmk8'  # 這裡是您 Google Forms 的連結
                    )
                ]
            )
        )

        line_bot_api.reply_message(event.reply_token, message)

    except:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤！'))


def sendPosition(event):  #位置資訊
    try:
        text1 = "地址：台北市信義區松壽路12號6樓(ATT 4 FUN百貨6F)"
        message = [
            TextSendMessage(  #顯示地址
                text = text1
            ),
            LocationSendMessage(  #顯示地圖
                title = "饗食天堂 台北信義店",
                address = text1,
                latitude = 25.03544606937841,
                longitude = 121.56606649576142
            ),
        ]
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))

def sendContact(event):  #真人服務
    try:
        message = TemplateSendMessage(
            alt_text = "真人服務",
            template = ButtonsTemplate(
                thumbnail_image_url='https://i.imgur.com/tVjKzPH.jpg',
                title='真人服務',
                text='有任何問題都可以打電話給我們喔',
                actions=[
                    URITemplateAction(label='撥打電話', uri='tel:02-7737-5889')  #開啟打電話功能
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))

def manageForm(event, mtext, user_id):  #處理LIFF傳回的FORM資料
    try:
        flist = mtext[3:].split('/')  #去除前三個「#」字元再分解字串  #取得輸入資料
        amount = flist[0]
        in_date = flist[1]
        in_time = flist[2]
        sql_cmd = "insert into booking (bid, roomamount, datein, timein) values('" + user_id + "', '" + amount + "', '" + in_date + "', '" + in_time + "');"
        db.session.execute(text(sql_cmd))
        db.session.commit()
        text1 = "您已訂位成功，資料如下："
        text1 += "\n人數：" + amount
        text1 += "\n用餐日期：" + in_date
        text1 += "\n用餐時間：" + in_time
        message = TextSendMessage(  #顯示訂房資料
            text = text1
        )
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))
        
def sendYes(event, user_id):  #處理取消訂位
    try:
        sql_cmd = "delete from booking where bid='" + user_id + "'"
        db.session.execute(text(sql_cmd))
        db.session.commit()
        message = TextSendMessage(
            text = "您的用餐預訂已成功刪除。\n期待您再次訂位，謝謝！"
        )
        line_bot_api.reply_message(event.reply_token,message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))

def pushMessage(event, mtext):  ##推播訊息給所有顧客
    try:
        msg = mtext[6:]  #取得訊息
        sql_cmd = "select * from hoteluser"
        query_data = db.session.execute(text(sql_cmd)).fetchall()
        userall = list(query_data)
        for user in userall:  #逐一推播
            message = TextSendMessage(
                text = msg
            )
            line_bot_api.push_message(to=user[1], messages=[message])  #推播訊息
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='發生錯誤！'))

if __name__ == '__main__':
    app.run()