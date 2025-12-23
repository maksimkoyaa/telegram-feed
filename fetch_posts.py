#!/usr/bin/env python3
"""
Скрипт для парсинга постов из Telegram канала для сайта.
Логика фильтрации:
1. Ищет посты, пока не наберет WANTED_POSTS_COUNT штук.
2. Пропускает посты без картинки.
3. Пропускает посты короче MIN_POST_LENGTH символов.
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- КОНФИГУРАЦИЯ ---
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', 'itmaksimkoya')
WANTED_POSTS_COUNT = 3  # Сколько постов нужно найти для сайта
MIN_POST_LENGTH = 100   # Минимальная длина текста (чтобы отсеять "Доброе утро" и т.д.)

def get_accurate_stats(post_link):
    """
    Делает дополнительный запрос к embed-версии поста, 
    чтобы получить точные просмотры и реакции.
    """
    try:
        # mode=tme притворяется клиентом Telegram для получения свежих данных
        embed_url = f"{post_link}?embed=1&mode=tme"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f'https://t.me/{CHANNEL_USERNAME}'
        }
        
        response = requests.get(embed_url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return None, []

        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. Парсим точные просмотры
        views = None
        views_elem = soup.find('span', class_='tgme_widget_message_views')
        if views_elem:
            views = views_elem.get_text(strip=True)
            
        # 2. Парсим реакции
        reactions_list = []
        
        # Реакции могут быть в разных контейнерах в зависимости от версии верстки
        reactions_block = soup.find('div', class_='tgme_widget_message_reactions') or \
                          soup.find('div', class_='mw-reactions-container')
        
        if reactions_block:
            reaction_items = reactions_block.find_all('a', class_='tgme_widget_message_reaction')
            for item in reaction_items:
                emoji_elem = item.find('div', class_='tgme_widget_message_reaction_emoji')
                emoji = emoji_elem.get_text(strip=True) if emoji_elem else ""
                
                count_elem = item.find('div', class_='tgme_widget_message_reaction_count')
                count = count_elem.get_text(strip=True) if count_elem else "0"
                
                if emoji:
                    reactions_list.append({'emoji': emoji, 'count': count})
                    
        return views, reactions_list

    except Exception as e:
        print(f"Warning: Не удалось получить статистику для {post_link}: {e}")
        return None, []

def fetch_telegram_posts():
    """
    Сканирует ленту и отбирает посты, соответствующие критериям качества.
    Останавливается, когда найдено WANTED_POSTS_COUNT постов.
    """
    
    url = f'https://t.me/s/{CHANNEL_USERNAME}'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cache-Control': 'no-cache'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        all_posts = soup.find_all('div', class_='tgme_widget_message')
        
        if not all_posts:
            return []

        # Разворачиваем список, чтобы идти от Самых Новых к Старым
        posts_elements = reversed(all_posts)
        
        posts = []
        
        print(f"Начинаем сканирование постов (нужно найти: {WANTED_POSTS_COUNT})...")
        
        for post_elem in posts_elements:
            # === ГЛАВНОЕ УСЛОВИЕ ОСТАНОВКИ ===
            if len(posts) >= WANTED_POSTS_COUNT:
                break
            # =================================

            try:
                # --- 1. Сбор сырых данных ---
                link_elem = post_elem.find('a', class_='tgme_widget_message_date')
                if not link_elem: continue
                
                post_link = link_elem['href']
                post_id = post_link.split('/')[-1]
                
                # Текст
                text_elem = post_elem.find('div', class_='tgme_widget_message_text')
                text = text_elem.get_text(separator='\n', strip=True) if text_elem else ''
                
                # Картинка
                image = None
                photo_elem = post_elem.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_elem:
                    style = photo_elem.get('style', '')
                    if 'background-image:url' in style:
                        image = style.split("url('")[1].split("')")[0] if "url('" in style else None
                
                # Видео
                video = None
                video_elem = post_elem.find('video')
                if video_elem and video_elem.get('src'): video = video_elem['src']
                
                # --- 2. ФИЛЬТРАЦИЯ (Фейсконтроль) ---
                
                # Условие А: Нет картинки -> Пропускаем
                if not image:
                    # print(f"Skipped {post_id}: no image")
                    continue
                
                # Условие Б: Текст слишком короткий -> Пропускаем
                if len(text) < MIN_POST_LENGTH:
                    # print(f"Skipped {post_id}: too short ({len(text)} chars)")
                    continue
                
                # --- 3. Пост прошел проверку, обрабатываем ---
                
                # Обрезка для превью (если нужно)
                if len(text) > 200: text = text[:200] + '...'
                
                # Дата
                time_elem = post_elem.find('time')
                if time_elem and time_elem.get('datetime'):
                    post_date = datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
                    date_str = post_date.strftime('%d %B')
                    months = {'January': 'января', 'February': 'февраля', 'March': 'марта', 'April': 'апреля', 'May': 'мая', 'June': 'июня', 'July': 'июля', 'August': 'августа', 'September': 'сентября', 'October': 'октября', 'November': 'ноября', 'December': 'декабря'}
                    for eng, rus in months.items(): date_str = date_str.replace(eng, rus)
                else:
                    date_str = 'Недавно'
                
                content_type = 'text'
                if video: content_type = 'video'
                elif image: content_type = 'photo'
                
                # Запрашиваем точную статистику
                initial_views = "0"
                views_elem = post_elem.find('span', class_='tgme_widget_message_views')
                if views_elem: initial_views = views_elem.get_text(strip=True)
                
                real_views, real_reactions = get_accurate_stats(post_link)
                
                final_views = real_views if real_views else initial_views
                final_reactions = real_reactions
                
                post_data = {
                    'id': int(post_id),
                    'text': text,
                    'date': date_str,
                    'views': final_views,
                    'reactions': final_reactions,
                    'link': post_link,
                    'image': image,
                    'video': video,
                    'type': content_type
                }
                
                posts.append(post_data)
                print(f"Добавлен пост {post_id} (Текст: {len(text)} симв.)")
                
                # Пауза, чтобы не получить бан
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Ошибка при обработке поста: {e}")
                continue
        
        return posts
        
    except Exception as e:
        print(f"Критическая ошибка при получении постов: {e}")
        return []

def main():
    print(f"Канал: @{CHANNEL_USERNAME}")
    print(f"Фильтр: Картинка + Текст > {MIN_POST_LENGTH} символов")
    
    posts = fetch_telegram_posts()
    
    if posts:
        print(f"Итого отобрано: {len(posts)} постов.")
    else:
        print("Подходящие посты не найдены (возможно, на странице только короткие записи или кружочки).")
        posts = []
    
    output_data = {
        'channel': CHANNEL_USERNAME,
        'updated_at': datetime.now().isoformat(),
        'posts': posts
    }
    
    with open('posts.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("Файл posts.json успешно обновлён!")

if __name__ == '__main__':
    main()
