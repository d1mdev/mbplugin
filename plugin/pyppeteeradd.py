#!/usr/bin/python3
# -*- coding: utf8 -*-
import asyncio, time, re, json, subprocess, logging, shutil, os, sys, traceback
import win32gui, win32process, psutil
import pyppeteer  # PYthon puPPETEER
#import pprint; pp = pprint.PrettyPrinter(indent=4).pprint
import store, settings

# Какой бы ни был режим в mbplugin для всех сторониих модулей отключаем расширенное логирование
# иначе в лог польется все тоннами
[logging.getLogger(name).setLevel(logging.ERROR) for name in logging.root.manager.loggerDict]

def hide_chrome(hide=True):
    'Прячем или показываем окно хрома'
    def enumWindowFunc(hwnd, windowList):
        """ win32gui.EnumWindows() callback """
        text = win32gui.GetWindowText(hwnd).lower()
        className = win32gui.GetClassName(hwnd).lower()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:  #  ??? text.lower().find('chrome')>=0
            if (text != '' and 'remote-debugging-port' in ''.join(psutil.Process(pid).cmdline())
            and not text.startswith('msct') and not text.startswith('default') and 'восстановить' not in text):
                windowList.append((hwnd, text, className))
                logging.debug(f'enumWindowFunc:{text=}, {className=}')
        except Exception:
            pass
    myWindows = []
    # enumerate thru all top windows and get windows which are ours
    win32gui.EnumWindows(enumWindowFunc, myWindows)
    for hwnd, text, className in myWindows:
        _, _ = text, className  # dummy pylint
        win32gui.ShowWindow(hwnd, not hide)  # True-Show, False-Hide
        if hide:
            win32gui.MoveWindow(hwnd, -1000, -1000, -100, -200, True) # У скрытого окна бывают доп окна которые вылезают на экран
        else:
            win32gui.MoveWindow(hwnd, 80, 80, 980, 880, True) # Возвращаем нормальные координаты

async def launch_browser(storename, response_worker=None, disconnected_worker=None):
    hide_chrome_flag = str(store.options('show_chrome')) == '0' and store.options('logginglevel') != 'DEBUG'
    storefolder = store.options('storefolder')
    user_data_dir = os.path.join(storefolder,'puppeteer')
    profile_directory = storename
    chrome_executable_path = store.options('chrome_executable_path')
    if not os.path.exists(chrome_executable_path):
        chrome_paths = [p for p in settings.chrome_executable_path_alternate if os.path.exists(p)]
        if len(chrome_paths) == 0:
            logging.error('Chrome.exe not found')
            raise RuntimeError(f'Chrome.exe not found')
        chrome_executable_path = chrome_paths[0]
    kill_chrome()  # Превинтивно убиваем все наши хромы, чтобы не появлялось кучи зависших
    logging.info(f'Launch chrome from {chrome_executable_path}')
    launch_config = {
        'headless': False,
        'ignoreHTTPSErrors': True,
        'defaultViewport': None,
        'handleSIGINT':False,  # need for threading (https://stackoverflow.com/questions/53679905)
        'handleSIGTERM':False,  
        'handleSIGHUP':False,
        # TODO хранить параметр в ini
        'executablePath': chrome_executable_path,
        'args': [f"--user-data-dir={user_data_dir}", f"--profile-directory={profile_directory}",
                 '--wm-window-animations-disabled',
                 '--no-sandbox',
                 '--disable-setuid-sandbox',
                 '--disable-dev-shm-usage',
                 '--disable-accelerated-2d-canvas',
                 '--no-first-run',
                 '--no-zygote',
                 '--log-level=3', # no logging                 
                 #'--single-process', # <- this one doesn't works in Windows
                 '--disable-gpu', 
                 "--window-position=-2000,-2000" if hide_chrome_flag else "--window-position=80,80"],
    }
    if store.options('proxy_server').strip() != '':
        launch_config['args'].append(f'--proxy-server={store.options("proxy_server").strip()}')
    browser = await pyppeteer.launch(launch_config)
    if hide_chrome_flag:
        hide_chrome()

    pages = await browser.pages()
    for page in pages[1:]:
        await page.close() # Закрываем остальные страницы, если вдруг открыты
    page = pages[0]  # await browser.newPage()
    if response_worker is not None:
        page.on("response", response_worker) # вешаем обработчик на страницы
    if disconnected_worker is not None:
        browser.on("disconnected", disconnected_worker) # вешаем обработчик закрытие браузера
    return browser, page

def kill_chrome():
    '''Киляем дебажный хром если вдруг какой-то висит, т.к. народ умудряется запускать не только хром, то имя exe возьмем из пути '''
    chrome_executable_path = store.options('chrome_executable_path')
    pname = os.path.split(chrome_executable_path)[-1].lower()
    for p in psutil.process_iter():
        try:
            if p.name().lower()==pname and 'remote-debugging-port' in ''.join(p.cmdline()):
                p.kill()    
        except Exception:
            pass

def clear_cache(storename):
    'Очищаем папку с кэшем профиля чтобы не разрастался'
    #return  # С такой очисткой оказывается связаны наши проблемы с загрузкой
    storefolder = store.options('storefolder')
    profilepath = os.path.abspath(os.path.join(storefolder, 'puppeteer', storename))  
    shutil.rmtree(os.path.join(profilepath, 'Cache'), ignore_errors=True)
    shutil.rmtree(os.path.join(profilepath, 'Code Cache'), ignore_errors=True)
    shutil.rmtree(os.path.join(profilepath, 'Service Worker', 'CacheStorage'), ignore_errors=True)

def delete_profile(storename):
    'Удаляем профиль'
    kill_chrome()  # Перед удалением киляем хром
    storefolder = store.options('storefolder')
    profilepath = os.path.abspath(os.path.join(storefolder, 'puppeteer', storename))    
    shutil.rmtree(profilepath)

async def page_evaluate(page, eval_string, default=None):
    'Безопасный eval - не падает при ошибке а возвращает None'
    try:
        if eval_string == '': 
            return default
        logging.debug(f'page.eval: {repr(eval_string)}')
        if str(store.options('log_full_eval_string')) == '0':
            eval_string_log = eval_string if len(eval_string)<200 else eval_string[:100]+'...'+eval_string[-100:]
            if 'password' in eval_string:
                eval_string_log = eval_string.split('password')[0]+'password ....'            
        else:
            eval_string_log = eval_string
        logging.info(f'page.eval: {repr(eval_string_log)}')
        res = await page.evaluate(eval_string)
        return res
    except Exception:
        logging.info(f'page.eval fail: {repr(eval_string_log)}')
        exception_text = f'Ошибка page.eval: {"".join(traceback.format_exception(*sys.exc_info()))}'
        logging.info(exception_text)        
        return default

async def page_reload(page, reason=''):
    logging.info(f'page.reload {reason}')
    await page.reload()

async def page_goto(page, url):
    logging.info(f'page.goto {url}')
    try:
        await page.goto(url, {'timeout': 10000})
    except pyppeteer.errors.TimeoutError:
        logging.info(f'page.goto timeout')
    # await asyncio.sleep(3)  # Ждем 3 секунды 
    # if await page_evaluate(page, 'setTimeout(function(){},1)<2'):
    # try:
    #    await page.waitForNavigation({'timeout': 20000})
    # except pyppeteer.errors.TimeoutError:   
    #    logging.info(f'waitForNavigation timeout')


async def do_waitfor(page, waitfor, tokens, wait_and_reload=10, wait_loop=30):
    ''' Ждем пока прогрузятся все интересующие страницы с данными
    wait_and_reload секунд ждем потом перезагружаем страницу
    wait_loop секунд ждем и уходим '''
    waitfor.update(tokens)
    logging.info(f'Start wait {waitfor}')
    for countdown in range(wait_loop):  
        if len(waitfor) == 0: break
        logging.debug(f'Wait {waitfor} {countdown}')
        await asyncio.sleep(1) 
        if countdown == wait_and_reload:
            # так и не дождались - пробуем перезагрузить и еще подождать
            await page_reload(page, 'Not all page were received (do_waitfor)')
    logging.info(f'End wait {waitfor}')        


class balance_over_puppeteer():
    '''Основная часть общих действий вынесена сюда см mosenergosbyt для примера использования '''

    def check_browser_opened_decorator(func):  # pylint: disable=no-self-argument
        async def wrapper(self, *args, **kwargs):
            if self.browser_open:
                res = await func(self, *args, **kwargs)  # pylint: disable=not-callable
                return res
            else:
                logging.error(f'Browser was not open')
                raise RuntimeError(f'Browser was not open')
        return wrapper

    def __init__(self,  login, password, storename=None, wait_loop=30, wait_and_reload=10, login_attempt=1):
        self.browser_open = True  # флаг что браузер рабобтает
        self.wait_loop = wait_loop  # TODO подобрать параметр
        self.login_attempt = login_attempt
        self.wait_and_reload = wait_and_reload
        self.password = password
        self.login_ori, self.acc_num = login, ''
        self.login = login
        self.storename = storename
        if '/' in login:
            self.login, self.acc_num = self.login_ori.split('/')
            # !!! в storename уже преобразован поэтому чтобы выкинуть из него ненужную часть нужно по ним тоже регуляркой пройтись
            self.storename = self.storename.replace(re.sub(r'\W', '_', self.login_ori), re.sub(r'\W', '_', self.login))  # исправляем storename
        clear_cache(self.storename)
        self.result = {}
        self.responses = {}

    async def response_worker(self, response):
        'Response Worker вызывается на каждый url который открывается при загрузке страницы (т.е. список тот же что на вкладке сеть в хроме)'
        'Проходящие запросы, которые json сохраняем в responses'
        if response.status == 200:
            try:
                data = await response.json()  # Берем только json
            except Exception:
                return
            try:
                post = ''
                if response.request.method == 'POST' and response.request.postData is not None:
                    post = response.request.postData
                self.responses[f'{response.request.method}:{post} URL:{response.request.url}$'] = data
                # TODO Сделать какой-нибудь механизм для поиска по загруженным страницам
                # txt = await response.text()
                # if '2336' in txt:
                #    logging.info(f'2336 in {response.request.url}')
            except:
                exception_text = f'Ошибка: {"".join(traceback.format_exception(*sys.exc_info()))}'
                logging.debug(exception_text)

    async def disconnected_worker(self):
        'disconnected_worker вызывается когда закрыли браузер'
        logging.info(f'Browser was closed')
        self.browser_open = False  # выставляем флаг

    # потом наверно перенесем их совсем сюда, а отдельные прибьем
    @check_browser_opened_decorator
    async def page_evaluate(self, eval_string, default=None):
        ''' переносим вызов в класс для того чтобы каждый раз не указывать page'''
        return (await page_evaluate(self.page, eval_string, default=None))

    @check_browser_opened_decorator
    async def page_goto(self, url):
        ''' переносим вызов в класс для того чтобы каждый раз не указывать page'''
        return (await page_goto(self.page, url))

    @check_browser_opened_decorator
    async def page_reload(self, reason=''):
        ''' переносим вызов в класс для того чтобы каждый раз не указывать page'''
        return (await page_reload(self.page, reason=''))

    @check_browser_opened_decorator
    async def page_type(self, selector, text, *args, **kwargs):
        'Безопасный type - не падает при ошибке а возвращает None'
        try:
            if selector != '' and text != '': 
                logging.info(f'page.type: {repr(selector)}')
                return await self.page.type(selector, text, *args, **kwargs)
        except Exception:
            logging.info(f'page.type fail: {repr(selector)}')

    @check_browser_opened_decorator
    async def page_click(self, selector, *args, **kwargs):
        'Безопасный click - не падает при ошибке а возвращает None'
        try:
            if selector != '': 
                logging.info(f'page.click: {repr(selector)}')
                return await self.page.click(selector, *args, **kwargs)
        except Exception:
            logging.info(f'page.click fail: {repr(selector)}')

    @check_browser_opened_decorator
    async def page_waitForNavigation(self, *args, **kwargs):
        'Безопасный waitForNavigation - не падает при ошибке а возвращает None'
        try:
            # большой таймаут и нельзя, а то некоторые страницы злоупотребляют тем что никогда не открываются до конца
            # поэтому ставим 10 сек. На краяняк через 10 сек само отвалится и к этому времени скорее всего откроется
            logging.info(f'page.waitForNavigation')
            return await self.page.waitForNavigation({'timeout': 10000})
        except pyppeteer.errors.TimeoutError:   
            logging.info(f'page.waitForNavigation timeout')

    # !!! TODO есть page.waitForSelector - покопать в эту сторону
    @check_browser_opened_decorator
    async def page_waitForSelector(self, selector, *args, **kwargs):
        'Безопасный waitForSelector - не падает при ошибке а возвращает None'
        try:
            if selector != '': 
                logging.info(f'page.waitForSelector: {repr(selector)}')
                return await self.page.waitForSelector(selector, {'timeout': 10000})
        except Exception:
            logging.info(f'page.waitForSelector fail: {repr(selector)}')  
            return None

    @check_browser_opened_decorator
    async def do_logon(self, url,user_selectors={}):
        'Делаем заход в личный кабинет/ проверяем не залогинены ли уже'
        'На вход передаем словарь селекторов и скриптов который перекроет действия по умолчанию'
        'Если какой-то из шагов по умолчанию хотим пропустить, передаем пустую строку'
        'Смотрите актуальное описание напротив параметров в коментариях'
        'Чтобы избежать ошибок - копируйте названия параметров'
        # Селекторы и скрипты по умолчанию
        selectors = {
                    'chk_lk_page_js': "document.querySelector('form input[type=password]') == null",  # true если мы в личном кабинете
                    'chk_login_page_js': "document.querySelector('form input[type=password]') !== null",  # true если мы в окне логина
                    'before_login_js': '',  # Команда которую надо выполнить перед вводом логина
                    'login_clear_js': "document.querySelector('form input[type=text]').value=''",  # команда для очистки поля логина
                    'login_selector': 'form input[type=text]',   # селектор поля ввода логина
                    'chk_submit_after_login_js': "",  # проверка нужен ли submit после логина
                    'submit_after_login_js': "document.querySelector('form [type=submit]').click()",  # Если после ввода логина нужно нажать submit через js
                    'submit_after_login_selector': "",  # или через селектор
                    'password_clear_js': "document.querySelector('form input[type=password]').value=''",  # команда на очистку поля пароля
                    'password_selector': 'form input[type=password]',  # селектор для поля пароля
                    'remember_checker': "",  # "document.querySelector('form input[name=remember]').checked==false",  # Проверка что флаг remember me не выставлен
                    'remember_js': "",  # "document.querySelector('form input[name=remember]').click()",  # js для выставления remember me
                    'remember_selector': "",  # 'form input[name=remember]',  # селектор для выставления remember me (не указывайте оба сразу а то может кликнуть два раза)
                    'captcha_checker': "",  # проверка что на странице капча у MTS - document.querySelector("div[id=captcha-wrapper]")!=null
                    'submit_selector': '',  # селектор для нажатия на финальный submit
                    'submit_js': "document.querySelector('form [type=submit]').click()"  # js для нажатия на финальный submit
        }
        # проверяем что все поля из user_selectors есть в селектор (если не так то скорее всего опечатка и надо сигналить)
        if set(user_selectors)-set(selectors) != set():
            logging.error(f'Не все ключи из user_selectors есть в selectord. Возможна опечатка, проверьте {set(user_selectors)-set(selectors)}')
        selectors.update(user_selectors)
        await self.page_goto(url)
        await self.page_waitForNavigation()
        if not await self.page_evaluate(selectors['chk_lk_page_js']) and not await self.page_evaluate(selectors['chk_login_page_js']):
            # Мы не в личном кабинете и не на странице логона - попробуем обновить страницу
            await self.page_reload('Not open login page')
            await asyncio.sleep(10)
        # Logon form
        if await self.page_evaluate(selectors['chk_lk_page_js']):
            logging.info(f'Already login')
        else:
            # Почему-то иногда с первого раза логон не проскакивает, тогда можно задать несколько login_attempt
            for cnt in range(self.login_attempt):
                if await self.page_evaluate(selectors['chk_login_page_js']):
                    logging.info(f'Login')
                    await self.page_evaluate(selectors['before_login_js'])  # Если задано какое-то действие перед логином - выполняем
                    await self.page_waitForSelector(selectors['login_selector'])  # Ожидаем наличия поля логина
                    await self.page_evaluate(selectors['login_clear_js'])  # очищаем поле логина
                    await self.page_type(selectors['login_selector'], self.login, {'delay': 10})  # вводим логин
                    if (await self.page_evaluate(selectors['chk_submit_after_login_js'], default=False)):  # Если нужно после логина нажать submit
                        await self.page_click(selectors['submit_after_login_selector']) # либо click
                        await self.page_evaluate(selectors['submit_after_login_js'])  # либо через js
                        await self.page_waitForSelector(selectors['password_selector'])  # и ждем появления поля с паролем
                        await asyncio.sleep(1)
                    await self.page_evaluate(selectors['password_clear_js'])  # очищаем поле пароля           
                    await self.page_type(selectors['password_selector'], self.password, {'delay': 10})  # вводим пароль
                    if await self.page_evaluate(selectors['remember_checker'], default=False):  # Если есть невыставленный check remember me
                        await self.page_evaluate(selectors['remember_js'])  # выставляем его
                        await self.page_click(selectors['remember_selector'], {'delay': 10})
                    await asyncio.sleep(1)
                    await self.page_click(selectors['submit_selector']) #  нажимаем на submit form
                    await self.page_evaluate(selectors['submit_js'])  # либо через js (на некоторых сайтах один из вариантов не срабатывает)
                    await self.page_waitForNavigation()  # ждем отработки нажатия
                    await asyncio.sleep(1)
                if await self.page_evaluate(selectors['chk_lk_page_js']):
                    logging.info(f'Logoned')
                    break 
                await asyncio.sleep(1)
                if cnt==10:  # На 10 попытку перезагружаем страницу
                    await self.page_reload('unclear: logged in or not')
            else:
                # Проверяем - это не капча ?
                if await self.page_evaluate(selectors['captcha_checker'], False):
                    # Если стоит флаг показывать капчу то включаем видимость хрома и ждем заданное время
                    if str(store.options('show_captcha')) == '1':
                        logging.info('Show captcha')
                        hide_chrome(hide=False)
                        for cnt2 in range(int(store.options('max_wait_captcha'))):
                            if not await self.page_evaluate(selectors['captcha_checker'], False):
                                break
                            await asyncio.sleep(1)
                        else:  # Капчу так никто и не ввел
                            logging.error(f'Show captcha timeout. A captcha appeared, but no one entered it')        
                            raise RuntimeError(f'A captcha appeared, but no one entered it')
                    else:  # Показ капчи не зададан выдаем ошибку и завершаем
                        logging.error(f'Сaptcha appeared')        
                        raise RuntimeError(f'Сaptcha appeared')
                else:
                    # Никуда не попали и это не капча
                    logging.error(f'Unknown state')
                    raise RuntimeError(f'Unknown state')

    @check_browser_opened_decorator
    async def wait_params(self, params, url='', save_to_result=True):
        ''' Переходим по url и ждем параметры
        ---
        url если url пустой то не переходим а просто производим действия на текущей странице
        --- 
        params - список словарей вида 
        {'name':'text', 'url_tag':['text1','text2'], 'pformula':'text'} - ожидается приход json с урлом содержащим все строки из  url_tag из этого json через python eval возьмем tag_pformula
        либо 
        {'name':'text', 'url_tag':['text'], 'jsformula':'text'} - ожидается приход json с урлом содержащим url_tag из этого json через js eval возьмем tag_jformula
        либо
        {'name':'text', 'url_tag':[], 'jsformula':'text'} - url_tag - пустой список или не указан, на странице выполняется js из jsformula
        Если нужно указать что в url_tag url заканчивается этим текстом, то поставьте после него знак $
        результат во всех случаях записывается с именем name в результирующий словарь
        Если параметр необязательный (т.е. его может и не быть) то чтобы его не ждать можно добавить в словарь по данному параметру 'wait':False
        #param если параметр не нужен а просто нужно выполнить действие, то в начале такого параметра ставим # 
        ---
        save_to_result=True то записываем их в итоговый словарь результатов (все, которые не начинаются с решетки) (self.result) 
        и также результаты возвращаем в словаре (return result) 
        ВАЖНО
        Из того что уже вылезло - если возникают проблемы со сложным eval надо завернуть его в ()=>{...;return ...}
        '''
        result = {}
        if len([i for i in params if 'name' not in i])>0:
            error_msg = f'Not all params have name param: {params}'
            logging.error(error_msg)
            raise RuntimeError(error_msg)
        if url != '':  # Если указан url то сначала переходим на него
            await self.page_goto(url)
            await self.page_waitForNavigation()
        for countdown in range(self.wait_loop): 
            await asyncio.sleep(1)
            for param in params:
                if param.get('url_tag', []) != []:  # Ищем в загруженных страницах
                    response_result_ = [v for k,v in self.responses.items() if [i for i in param['url_tag'] if i not in k]==[]]
                    if len(response_result_)>0:
                        response_result = response_result_[0]
                        if param.get('pformula','') != '':
                            logging.info(f'pformula on {param["url_tag"]}:{param["pformula"]}')
                            # Для скрипта на python делаем 
                            try:
                                res = eval(param['pformula'], {'data':response_result})
                                if res is not None:
                                    result[param['name']] = res
                            except Exception:
                                exception_text = f'Ошибка в pformula:{param["pformula"]} :{"".join(traceback.format_exception(*sys.exc_info()))}'
                                logging.info(exception_text)    
                        if param.get('jsformula', '') != '':
                            logging.info(f'jsformula on {param["url_tag"]}:{param["jsformula"]}')
                            res = await self.page_evaluate(f"()=>{{data={json.dumps(response_result,ensure_ascii=False)};return {param['jsformula']};}}")
                            if res is not None:
                                result[param['name']] = res
                else:  # Ищем на самой странице - запускаем js
                    logging.info(f'jsformula on url {self.page.url}:{param["jsformula"]}')
                    content = await self.page.content()
                    self.responses[f'CONTENT URL:{self.page.url}$'] = content
                    res = await self.page_evaluate(param['jsformula'])
                    if res is not None:
                        result[param['name']] = res
            # Если все обязательные уже получили
            if {i['name'] for i in params if i.get('wait',True)} - set(result) == set():
                break  # выходим если все получили
            if countdown == self.wait_and_reload:
                # так и не дождались - пробуем перезагрузить и еще подождать
                await self.page_reload('Data not received')        
        else:  # время вышло а получено не все - больше не ждем 
            no_receved_keys = {i['name'] for i in params} - set(result)
            logging.error(f'Not found all param on {url}: {",".join(no_receved_keys)}')
        if save_to_result:
            self.result.update({k:v for k,v in result.items() if not k.startswith('#')})  # Не переносим те что с решеткой в начале
        return result

    async def _async_main(self):
        self.browser, self.page = await launch_browser(self.storename, response_worker=self.response_worker, disconnected_worker=self.disconnected_worker)
        await self.async_main()  # !!! CALL async_main
        logging.debug(f'Data ready {self.result.keys()}')
        if str(store.options('log_responses')) == '1' or store.options('logginglevel') == 'DEBUG':
            import pprint
            text = '\n\n'.join([f'{k}\n{v if k.startswith("CONTENT") else pprint.PrettyPrinter(indent=4).pformat(v) }'
                                for k, v in self.responses.items() if 'GetAdElementsLS' not in k and 'mc.yandex.ru' not in k])
            open(os.path.join(store.options('loggingfolder'), self.storename + '.log'), 'w', encoding='utf8', errors='ignore').write(text)
        await self.browser.close()
        kill_chrome()  # Добиваем  все наши незакрытые хромы, чтобы не появлялось кучи зависших
        clear_cache(self.storename)
        return self.result

    async def async_main(self):
        pass

    def main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.get_event_loop().run_until_complete(self._async_main())
        return self.result   
