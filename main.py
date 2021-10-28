import os
import time
import base64
import json
import re
import requests as rq
from bs4 import BeautifulSoup as bs
import cv2


class InterparkTicket:
    def __init__(self, user_id, user_pw):
        self.user_id = user_id
        self.user_pw = user_pw
        self.s = rq.Session()
        self.set_session()
        self.bookmain = None
        self.sessid = None
        self.parsername = "html.parser"

    def set_session(self):
        self.s.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.70 Safari/537.36",
             "sec-ch-ua": '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"', "sec-ch-ua-mobile": "?0"})
        #  "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"})
        # self.s.verify = False
        # proxies = {
        #     "http": "http://172.21.64.1:8888",
        #     "https": "http://172.21.64.1:8888"
        # }
        # self.s.proxies.update(proxies)

    def login(self):
        resp = self.s.get("https://ticket.interpark.com/Gate/TPLogOut.asp?From=T&tid1=main_gnb&tid2=right_top&tid3=logout&tid4=logout")
        open("tplogout.html", "w").write(resp.text)
        soup = bs(resp.text, self.parsername)
        iframe = soup.find("iframe")
        src = iframe['src']

        resp = self.s.get(src)
        open("form.html", "w").write(resp.text)
        soup = bs(resp.text, self.parsername)
        form = soup.select("#loginFrm")
        data = {}
        for element in form[0].find_all('input'):
            try:
                data[element['name']] = element['value']
            except KeyError:
                pass
        headers = {
            "Referer": "https://accounts.interpark.com/login/form"
        }

        data.update({"userId": self.user_id, "userPwd": self.user_pw})
        resp = self.s.post("https://accounts.interpark.com/login/submit", headers=headers, data=data)
        open("submit.html", "w").write(resp.text)
        if "var isOtpErrorr = true" in resp.text:
            raise rq.exceptions.RequestException("login error")

    def get_matches(self):
        resp = self.s.get("http://ticket.interpark.com/Contents/Promotion/2021/Event/leagueOflegendChampionsKorea")
        open("match_list.html", "w").write(resp.text)

        soup = bs(resp.text, self.parsername)
        return soup.select(".reservation")

    def get_bookmain(self, match_elem):
        params = re.findall("'(.*?)'", match_elem['onclick'])
        if len(params) != 9 or params[1] != 'Y' or params[2] != 'G2005':
            raise ValueError("wrong func param")
        params = params[3:]
        params.insert(5, "")
        names = ["GroupCode", "Tiki", "PlayDate", "PlaySeq", "Point", "BizCode", "BizMemberCode"]
        data = dict(zip(names, params))
        headers = {
            "Referer": "http://ticket.interpark.com",
            "Upgrade-Insecure-Requests": "1"
        }
        resp = self.s.post("http://poticket.interpark.com/Book/BookSession.asp", data=data, headers=headers)
        open("book_session.html", "w").write(resp.text)
        soup = bs(resp.text, self.parsername)
        form = soup.select("form")
        data = {}
        for element in form[0].find_all('input'):
            try:
                data[element['name']] = element['value']
            except KeyError:
                pass
        src = form[0]["action"]

        resp = self.s.post(src, data=data)
        open("book_main.html", "w").write(resp.text)
        self.bookmain = resp.text

    def booking(self):
        if self.bookmain is None:
            raise ValueError("call get_bookmain first")
        soup = bs(self.bookmain, self.parsername)
        form = soup.select("#ifrmBookStep")
        src = form[0]["src"]

        resp = self.s.get("http://poticket.interpark.com" + src)
        open("book_datetime.html", "w").write(resp.text)

        form = soup.select("#formBook")
        data = {}
        for element in form[0].find_all('input'):
            try:
                data[element['name']] = element['value']
            except KeyError:
                pass

        resp = self.s.post("http://poticket.interpark.com/Book/BookSeat.asp", data=data)
        open("book_seat.html", "w").write(resp.text)

    def get_captcha(self):
        if self.bookmain is None:
            raise ValueError("call get_bookmain first")
        soup = bs(self.bookmain, self.parsername)
        form = soup.select("#SessionId")
        self.sessid = form[0]["value"]

        t = time.time()
        url = f"https://poticket.interpark.com/CommonAPI/Captcha/IPCaptcha?p2={self.sessid}&p1={time.strftime('%Y%m%d%H%M%S00')}&callback=jsonCallback&_={int(t * 10)}"
        resp = self.s.get(url)
        m = re.search(r'\{.*\}', resp.text)
        data = json.loads(m.group())
        m = re.search(r',(.*)', data['Img'])
        img_data = m.group(1)
        with open(f"imgs/{self.sessid}.capt.jpg", "wb") as f:
            f.write(base64.b64decode(img_data))

    def convert_captcha(self):
        img = cv2.imread(f'imgs/{self.sessid}.capt.jpg')

        # colors = []
        x_max, y_max, z = img.shape
        for x in range(x_max):
            for y in range(y_max):
                b, g, r = img[x, y].tolist()

                N = 4
                q_b = round(b*(N/255)) * (255/N)
                q_g = round(g*(N/255)) * (255/N)
                q_r = round(r*(N/255)) * (255/N)
                img[x, y] = (q_b, q_g, q_r)

                # cv2.imwrite('process.jpg', qimg)

        #         color_arr = img[x, y].tolist()
        #         hexcode = f"#{color_arr[2]:02x}{color_arr[1]:02x}{color_arr[0]:02x}"
        #         if hexcode not in colors:
        #             colors.append(hexcode)
        # colors.sort()
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)

        img = cv2.medianBlur(img, 3)
        # img = cv2.Canny(img, 100, 200)
        cv2.imwrite(f'imgs/{self.sessid}.mod.jpg', img)
        # for color in colors:
        #     print(f"body {{color: {color}}}")
        # print(len(colors))
        # print(colors)
    
    def read_captcha(self):
        os.system(f"tesseract imgs/{self.sessid}.mod.jpg imgs/{self.sessid}.result.txt")


if __name__ == "__main__":
    it = InterparkTicket("id", "pw")
    it.login()
    match_list = it.get_matches()
    for match in match_list:
        it.get_bookmain(match)
        it.booking()
        it.get_captcha()
        it.convert_captcha()
        it.read_captcha()
