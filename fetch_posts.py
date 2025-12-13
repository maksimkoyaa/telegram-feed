#!/usr/bin/env python3
"""
Скрипт для получения последних постов из Telegram канала через веб-скрейпинг.
Включает парсинг просмотров и реакций.
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Получаем переменные из GitHub Secrets или используем дефолтные
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', 'itmaksimkoya')
POSTS_TO_FETCH = 3

def fetch_telegram_posts():
    """Получает последние посты из Telegram канала через веб-версию"""
    
    # URL веб-версии канала
    url = f'https://t.me/s/{CHANNEL_USERNAME}'
    
    try:
        # Делаем запрос
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Парсим HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. Находим ВСЕ посты на странице (без лимита, чтобы найти низ страницы)
        all_posts = soup.find_all('div', class_='tgme_widget_message')
        
        if not all_posts:
            print("Посты не найдены на странице.")
            return []

        # 2. Берем срез последних N постов
        # (в HTML телеграма старые сверху, новые снизу)
        posts_elements = all_posts[-POSTS_TO_FETCH:]
        
        # 3. Разворачиваем, чтобы самый свежий был первым в JSON (индекс 0)
        posts_elements = reversed(posts_elements)
        
        posts = []
        
        for post_elem in posts_elements:
            try:
                # --- Базовая информация ---
                
                # Извлекаем ID поста из ссылки
                link_elem = post_elem.find('a', class_='tgme_widget_message_date')
                if not link_elem:
                    continue
                    
                post_link = link_elem['href']
                post_id = post_link.split('/')[-1]
                
                # Извлекаем текст
                text_elem = post_elem.find('div', class_='tgme_widget_message_text')
                text = text_elem.get_text(strip=True) if text_elem else ''
                
                # Ограничиваем длину текста для превью
                if len(text) > 200:
                    text = text[:200] + '...'
                
                # Извлекаем дату
                time_elem = post_elem.find('time')
                if time_elem and time_elem.get('datetime'):
                    post_date = datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
                    date_str = post_date.strftime('%d %B')
                    # Переводим месяц на русский
                    months = {
                        'January': 'января', 'February': 'февраля', 'March': 'марта',
                        'April': 'апреля', 'May': 'мая', 'June': 'июня',
                        'July': 'июля', 'August': 'августа', 'September': 'сентября',
                        'October': 'октября', 'November': 'ноября', 'December': 'декабря'
                    }
                    for eng, rus in months.items():
                        date_str = date_str.replace(eng, rus)
                else:
                    date_str = 'Недавно'
                
                # --- Статистика (Новое) ---
                
                # Парсим просмотры
                views = "0"
                views_elem = post_elem.find('span', class_='tgme_widget_message_views')
                if views_elem:
                    views = views_elem.get_text(strip=True)

                # Парсим реакции
                reactions_list = []
                reactions_block = post_elem.find('div', class_='tgme_widget_message_reactions')
                if reactions_block:
                    reaction_items = reactions_block.find_all('a', class_='tgme_widget_message_reaction')
                    for item in reaction_items:
                        emoji_elem = item.find('div', class_='tgme_widget_message_reaction_emoji')
                        emoji = emoji_elem.get_text(strip=True) if emoji_elem else ""
                        
                        count_elem = item.find('div', class_='tgme_widget_message_reaction_count')
                        count = count_elem.get_text(strip=True) if count_elem else "0"
                        
                        if emoji:
                            reactions_list.append({'emoji': emoji, 'count': count})

                # --- Медиа ---
                
                # Извлекаем изображение
                image = None
                photo_elem = post_elem.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_elem:
                    style = photo_elem.get('style', '')
                    if 'background-image:url' in style:
                        # Извлекаем URL из style="... background-image:url('...')..."
                        image = style.split("url('")[1].split("')")[0] if "url('" in style else None
                
                # Извлекаем видео
                video = None
                video_elem = post_elem.find('video')
                if video_elem and video_elem.get('src'):
                    video = video_elem['src']
                
                # Определяем тип контента
                content_type = 'text'
                if video:
                    content_type = 'video'
                elif image:
                    content_type = 'photo'
                
                # Сборка данных
                post_data = {
                    'id': int(post_id),
                    'text': text,
                    'date': date_str,
                    'views': views,           # Просмотры
                    'reactions': reactions_list, # Реакции
                    'link': post_link,
                    'image': image,
                    'video': video,
                    'type': content_type
                }
                
                posts.append(post_data)
                
            except Exception as e:
                print(f"Ошибка при обработке поста: {e}")
                continue
        
        return posts
        
    except Exception as e:
        print(f"Ошибка при получении постов: {e}")
        return []

def main():
    """Основная функция"""
    print(f"Получаем посты из канала @{CHANNEL_USERNAME}...")
    
    posts = fetch_telegram_posts()
    
    if not posts:
        print("Не удалось получить посты или канал пуст!")
        posts = []
    else:
        print(f"Успешно получено постов: {len(posts)}")
        # Вывод для отладки (можно убрать)
        print(f"Последний пост ID: {posts[0]['id']}, Просмотры: {posts[0]['views']}")
    
    # Сохраняем в JSON
    output_data = {
        'channel': CHANNEL_USERNAME,
        'updated_at': datetime.now().isoformat(),
        'posts': posts
    }
    
    with open('posts.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("Файл posts.json обновлён!")

if __name__ == '__main__':
    main()
