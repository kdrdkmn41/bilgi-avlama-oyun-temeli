import pygame
import random
import math
import sys
import os
import serial
import time

# --- SERİ PORT AYARLARI ---
SERIAL_PORT = 'COM7'  # <--- BURAYI ARDUINO'NUZA UYGUN PORT İLE DEĞİŞTİRİNİZ!
BAUD_RATE = 9600

ser = None
SERIAL_ENABLED = False


def init_serial():
    """Seri port bağlantısını kurar ve global değişkenleri ayarlar."""
    global ser, SERIAL_ENABLED
    try:
        # Bağlantıyı kur (Kısa zaman aşımı, oyunun kilitlenmesini önler)
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
        time.sleep(0.5)  # Arduino'nun resetlenmesini bekle (2 saniye çok uzun olabilir)
        print(f"✅ Seri port {SERIAL_PORT} başarıyla bağlandı. Kontroller aktif.")
        SERIAL_ENABLED = True
    except serial.SerialException:
        print(f"❌ HATA: Seri port {SERIAL_PORT} bulunamadı. Klavye kontrolü kullanılacak.")
        SERIAL_ENABLED = False


# Güvenli çıkış için tüm kodu bir try bloğuna alıyoruz.
try:
    init_serial()  # Program başlarken seri bağlantıyı dene

    # Pygame'i başlat
    pygame.init()

    # -------------------------
    # Sabitler ve Ayarlar
    # -------------------------
    WIDTH, HEIGHT = 1024, 600
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Eğitsel Balık Tutma Oyunu")

    CLOCK = pygame.time.Clock()

    # Font ayarları
    FONT = pygame.font.SysFont(None, 28, bold=True)
    FONT_QUESTION = pygame.font.SysFont(None, 36, bold=True)
    FONT_FISH = pygame.font.SysFont(None, 20)
    FONT_FEEDBACK = pygame.font.SysFont(None, 40, bold=True)

    # Hız Ayarları
    AUTO_SINK_SPEED = 0.5
    PULL_SPEED = 10.0
    HORIZONTAL_SPEED = 6.0

    # Zikzak İp Efekti Ayarları
    ZIGZAG_AMPLITUDE = 10
    ZIGZAG_FREQUENCY = 0.1

    # İp Salınım Efekti Ayarları
    SWAY_AMPLITUDE = 80.0
    SWAY_SPEED = 0.1

    # -------------------------
    # EĞİTSEL VERİLERİ DOSYADAN YÜKLEME
    # -------------------------
    QUESTION_DATA = []
    ALL_ANSWERS_AND_DISTRACTORS = []


    def load_questions_from_file(filename="questions.txt"):
        """Soruları, cevapları ve çeldiricileri dosyadan okur ve QUESTION_DATA'yı doldurur."""
        global QUESTION_DATA, ALL_ANSWERS_AND_DISTRACTORS
        QUESTION_DATA = []
        all_answers = set()

        # --- Yedek (Fallback) Soru Verileri ---
        DEFAULT_QUESTIONS = [
            {"question": "Yedek Soru: 1 + 1 kaç eder?", "answer": "2", "distractors": ["3", "4", "5", "6"]},
            {"question": "Yedek Soru: Pygame ne dilidir?", "answer": "Python",
             "distractors": ["C++", "Java", "Ruby", "C#"]},
        ]

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split('|')
                        if len(parts) < 3:
                            continue

                        question_text = parts[0].replace("SORU:", "").strip()
                        answer_text = parts[1].replace("CEVAP:", "").strip()
                        distractors_text = parts[2].replace("YANCILAR:", "").strip()
                        distractors_list = [d.strip() for d in distractors_text.split(',')]

                        if question_text and answer_text:
                            QUESTION_DATA.append({
                                "question": question_text,
                                "answer": answer_text,
                                "distractors": distractors_list
                            })
                            all_answers.add(answer_text)
                            all_answers.update(distractors_list)

                    except IndexError:
                        pass

        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Yedek verileri kullan
        if not QUESTION_DATA:
            QUESTION_DATA = DEFAULT_QUESTIONS
            for q in QUESTION_DATA:
                all_answers.add(q["answer"])
                all_answers.update(q["distractors"])

        ALL_ANSWERS_AND_DISTRACTORS = list(all_answers)


    # -------------------------
    # Görsellerin Ölçeklendirilmesi ve Yüklenmesi
    # -------------------------
    FISH_SIZE = (80, 40)
    background = None
    hook_img = None
    fish_sprites = []


    def create_fallback_fish(color):
        """Basit bir ok/üçgen şekliyle yedek balık yüzeyleri oluşturur."""
        surf1 = pygame.Surface(FISH_SIZE, pygame.SRCALPHA)
        surf2 = pygame.Surface(FISH_SIZE, pygame.SRCALPHA)
        pygame.draw.polygon(surf1, color, [(0, FISH_SIZE[1] // 2), (FISH_SIZE[0], 0), (FISH_SIZE[0], FISH_SIZE[1])])
        pygame.draw.polygon(surf2, color,
                            [(5, FISH_SIZE[1] // 2), (FISH_SIZE[0] - 5, 0), (FISH_SIZE[0] - 5, FISH_SIZE[1])])
        return [surf1, surf2]


    def load_assets():
        """Tüm oyun görsellerini yükler veya yedeklerini oluşturur."""
        global background, hook_img, fish_sprites

        # Arka plan
        try:
            background = pygame.image.load("assets/background.png").convert()
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
        except pygame.error:
            background = pygame.Surface((WIDTH, HEIGHT))
            background.fill((0, 100, 150))

        # Olta/Kanca görseli
        try:
            hook_img = pygame.image.load("assets/hook.png").convert_alpha()
            hook_img = pygame.transform.scale(hook_img, (40, 40))
        except pygame.error:
            hook_img = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(hook_img, (200, 200, 200), (20, 20), 15)

        # Balık görselleri
        try:
            fish_sprites.append([
                pygame.transform.scale(pygame.image.load("assets/fish1_1.png").convert_alpha(), FISH_SIZE),
                pygame.transform.scale(pygame.image.load("assets/fish1_2.png").convert_alpha(), FISH_SIZE)
            ])
            fish_sprites.append([
                pygame.transform.scale(pygame.image.load("assets/fish3_1.png").convert_alpha(), FISH_SIZE),
                pygame.transform.scale(pygame.image.load("assets/fish3_2.png").convert_alpha(), FISH_SIZE)
            ])
        except pygame.error:
            if not fish_sprites:
                fish_sprites.append(create_fallback_fish((255, 165, 0)))
                fish_sprites.append(create_fallback_fish((255, 192, 203)))


    load_assets()
    load_questions_from_file()

    # -------------------------
    # Oyun değişkenleri
    # -------------------------
    line_x = WIDTH // 2
    line_y = 50
    HOOK_INITIAL_X = WIDTH - 150
    hook_x_anchor = float(HOOK_INITIAL_X)
    hook_pos = [float(HOOK_INITIAL_X), float(line_y)]
    score = 0
    game_state = "MENU"
    caught_fish = None
    time_counter = 0
    feedback_timer = 0
    current_question_data = {}
    current_question = ""
    current_answer = ""


    # -------------------------
    # FONKSİYONLAR
    # -------------------------

    def new_question():
        global current_question_data, current_question, current_answer
        if not QUESTION_DATA:
            global game_state
            game_state = "MENU"
            return
        current_question_data = random.choice(QUESTION_DATA)
        current_question = current_question_data["question"]
        current_answer = current_question_data["answer"]
        possible_texts = [current_answer] + current_question_data["distractors"]
        texts_to_assign = possible_texts[:len(fishes)]
        while len(texts_to_assign) < len(fishes):
            if current_question_data["distractors"]:
                texts_to_assign.append(random.choice(current_question_data["distractors"]))
            else:
                texts_to_assign.append("...")
        random.shuffle(texts_to_assign)
        correct_fish_assigned = False
        for fish, text in zip(fishes, texts_to_assign):
            fish.text = text
            fish.is_correct = (text == current_answer)
            if fish.is_correct:
                correct_fish_assigned = True
        if not correct_fish_assigned and fishes:
            chosen_fish = random.choice(fishes)
            chosen_fish.text = current_answer
            chosen_fish.is_correct = True


    # -------------------------
    # BALIK SINIFI
    # -------------------------
    class Fish:
        def __init__(self, text=""):
            self.type = random.randint(0, len(fish_sprites) - 1)
            self.x = -FISH_SIZE[0]
            self.y = random.randint(line_y + 100, HEIGHT - 100)
            self.speed = random.uniform(1.5, 3.5)
            self.anim_frame = 0
            self.anim_timer = 0
            self.rect = pygame.Rect(self.x, self.y, FISH_SIZE[0], FISH_SIZE[1])
            self.caught = False
            self.fish_score_value = 1
            self.text = text
            self.is_correct = False

        def update(self):
            if self.caught:
                self.x = hook_pos[0] + 5
                self.y = hook_pos[1] - 10
                self.rect.topleft = (int(self.x), int(self.y))
                return
            self.x += self.speed
            self.rect.topleft = (int(self.x), int(self.y))
            if self.x > WIDTH + 100:
                self.reset_offscreen()
            self.anim_timer += 1
            if self.anim_timer >= 20:
                self.anim_frame = (self.anim_frame + 1) % len(fish_sprites[self.type])
                self.anim_timer = 0

        def draw(self, surf):
            img = fish_sprites[self.type][self.anim_frame]
            surf.blit(img, (int(self.x), int(self.y)))
            text_surf = FONT_FISH.render(self.text, True, (0, 0, 0))
            text_rect = text_surf.get_rect(midbottom=(int(self.x) + FISH_SIZE[0] // 2, int(self.y) - 5))
            surf.blit(text_surf, text_rect)

        def reset_offscreen(self):
            self.x = -FISH_SIZE[0]
            self.y = random.randint(line_y + 100, HEIGHT - 100)
            self.speed = random.uniform(1.5, 3.5)
            self.caught = False


    fishes = [Fish() for _ in range(7)]
    new_question()


    # -------------------------
    # Yakalama kontrolü
    # -------------------------
    def check_catch():
        """Kanca ve balık çarpışmasını kontrol eder."""
        global caught_fish
        if caught_fish:
            return False
        HOOK_WIDTH, HOOK_HEIGHT = hook_img.get_size()
        hook_rect = pygame.Rect(hook_pos[0] - HOOK_WIDTH // 2, hook_pos[1] - HOOK_HEIGHT // 2, HOOK_WIDTH, HOOK_HEIGHT)
        for fish in fishes:
            if not fish.caught and hook_rect.colliderect(fish.rect):
                fish.caught = True
                caught_fish = fish
                return True
        return False


    # -------------------------
    # Zikzaklı İpi Çizme
    # -------------------------
    def draw_zigzag_line(surf, start_pos, end_pos, color, width, time_counter):
        """Başlangıç noktasından bitiş noktasına zikzaklı ip çizer."""
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        distance = math.sqrt(dx ** 2 + dy ** 2)
        segment_length = 10
        num_points = max(2, int(distance / segment_length))
        points = [start_pos]
        for i in range(1, num_points):
            ratio = i / (num_points - 1)
            px = start_pos[0] + dx * ratio
            py = start_pos[1] + dy * ratio
            if distance > 0:
                angle = math.atan2(dy, dx)
                offset_x = ZIGZAG_AMPLITUDE * math.sin(ZIGZAG_FREQUENCY * i + time_counter) * math.sin(angle)
                offset_y = ZIGZAG_AMPLITUDE * math.sin(ZIGZAG_FREQUENCY * i + time_counter) * -math.cos(angle)
            else:
                offset_x, offset_y = 0, 0
            points.append((int(px + offset_x), int(py + offset_y)))
        points[-1] = end_pos
        if len(points) > 1:
            pygame.draw.lines(surf, color, False, points, width)


    # -------------------------
    # Menü
    # -------------------------
    def draw_menu():
        win.fill((20, 20, 40))
        title = FONT.render("Eğitsel Balık Tutma Oyunu", True, (255, 255, 255))

        if QUESTION_DATA:
            text = FONT.render("Başlamak için BOŞLUK (SPACE)", True, (200, 200, 200))
        else:
            text = FONT.render("HATA: Soru dosyası yüklenemedi. Kontrol edin.", True, (255, 50, 50))

        # Kontrol metnini seri bağlantı durumuna göre ayarla
        control_method_dikey = "KY-040'ı çevirerek" if SERIAL_ENABLED else "Yukarı/Aşağı ok tuşları"
        control_method_yatay = "Sürgülü Potansiyometre" if SERIAL_ENABLED else "Sol/Sağ ok tuşları"

        instruction1 = FONT.render(f"Dikey (Çek/Sal): {control_method_dikey}", True, (150, 150, 150))
        instruction2 = FONT.render(f"Yatay (Sağ/Sol): {control_method_yatay} veya Farenin Sol/Sağ Tuşları", True,
                                   (150, 150, 150))
        instruction3 = FONT.render("Doğru cevabı yakalayıp yüzeye çıkarın.", True, (150, 150, 150))

        title_rect = title.get_rect(center=(WIDTH // 2, 150))
        text_rect = text.get_rect(center=(WIDTH // 2, 300))
        inst1_rect = instruction1.get_rect(center=(WIDTH // 2, 400))
        inst2_rect = instruction2.get_rect(center=(WIDTH // 2, 450))
        inst3_rect = instruction3.get_rect(center=(WIDTH // 2, 500))

        win.blit(title, title_rect)
        win.blit(text, text_rect)
        win.blit(instruction1, inst1_rect)
        win.blit(instruction2, inst2_rect)
        win.blit(instruction3, inst3_rect)


    # -------------------------
    # OYUN DÖNGÜSÜ
    # -------------------------
    running = True
    while running:
        CLOCK.tick(60)
        time_counter += 1 * ZIGZAG_FREQUENCY

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Menüden oyuna geçiş
            if game_state == "MENU" and event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if not QUESTION_DATA:
                    continue

                game_state = "PLAY"
                hook_x_anchor = float(HOOK_INITIAL_X)
                hook_pos = [float(HOOK_INITIAL_X), float(line_y)]
                score = 0
                caught_fish = None
                for f in fishes:
                    f.reset_offscreen()
                new_question()

        if game_state == "MENU":
            draw_menu()
            pygame.display.update()
            continue

        # Arka planı çiz
        win.blit(background, (0, 0))

        keys = pygame.key.get_pressed()

        # -------------------------------------
        # Seri Porttan Veri Oku (KY-040 ve Potansiyometre Entegrasyonu)
        # -------------------------------------
        ky040_pull_down = 0  # Dikey hareket: 1(Yukarı), -1(Aşağı), 0(Yok)
        pot_value = -1  # Yatay değer: 0-1023, -1 (okunmadıysa)

        if SERIAL_ENABLED and ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                # Örn: Gelen veri: "D1,P512"

                if line:
                    parts = line.split(',')
                    for part in parts:
                        if part.startswith('D'):
                            ky040_pull_down = int(part[1:])
                        elif part.startswith('P'):
                            pot_value = int(part[1:])

            except Exception:
                ky040_pull_down = 0
                pot_value = -1

        # -------------------------------------
        # Kanca Hareketi (Yatay ve Dikey Kontroller)
        # -------------------------------------

        mouse_buttons = pygame.mouse.get_pressed()

        # YATAY HAREKET: Potansiyometre VEYA Klavye/Fare
        if pot_value != -1:
            # Potansiyometre değerini (0-1023) ekran genişliğine (WIDTH) map'le
            target_x_anchor = 10 + (pot_value / 1023.0) * (WIDTH - 20)

            # Hareketi yumuşatma
            smoothing_factor = 0.2
            hook_x_anchor = hook_x_anchor * (1 - smoothing_factor) + target_x_anchor * smoothing_factor

        else:
            # Klavye/Fare yatay kontrolü (Potansiyometre kapalı/okunamazsa)
            if mouse_buttons[0] or keys[pygame.K_LEFT]:
                hook_x_anchor -= HORIZONTAL_SPEED
            if mouse_buttons[2] or keys[pygame.K_RIGHT]:
                hook_x_anchor += HORIZONTAL_SPEED

        # İp Salınımı
        sway_offset = SWAY_AMPLITUDE * math.sin(time_counter * SWAY_SPEED)
        hook_pos[0] = hook_x_anchor + sway_offset
        # DİKEY HAREKET: KY-040 VEYA Klavye

        # KY-040 için çekme/salma faktörünü PULL_SPEED'den farklı ayarlayabilirsiniz
        KY040_PULL_FACTOR = PULL_SPEED  # Şu anki örnekte 20.0

        # YUKARI ÇEKME: Klavye (UP) VEYA KY-040 (1)
        if keys[pygame.K_UP]:
            hook_pos[1] -= PULL_SPEED
        elif ky040_pull_down == 1:
            hook_pos[1] -= KY040_PULL_FACTOR

        # AŞAĞI SALMA: Klavye (DOWN) VEYA KY-040 (-1)
        elif not caught_fish and keys[pygame.K_DOWN]:
            hook_pos[1] += PULL_SPEED
        elif not caught_fish and ky040_pull_down == -1:
            hook_pos[1] += KY040_PULL_FACTOR

        elif not caught_fish:
            hook_pos[1] += AUTO_SINK_SPEED  # Otomatik batma

        # Sınırlar
        hook_x_anchor = max(10, min(hook_x_anchor, WIDTH - 10))
        hook_pos[1] = max(line_y, min(hook_pos[1], HEIGHT - 30))

        # -------------------------------------
        # Yakalama ve Skor Kontrolü
        # -------------------------------------

        if caught_fish:
            if hook_pos[1] <= line_y:
                if caught_fish.is_correct:
                    score += caught_fish.fish_score_value
                    feedback_text = "DOĞRU! (+1 Puan)"
                    feedback_color = (0, 255, 0)
                    new_question()
                else:
                    score -= caught_fish.fish_score_value
                    feedback_text = "YANLIŞ! (-1 Puan)"
                    feedback_color = (255, 0, 0)

                feedback_timer = 90
                caught_fish.reset_offscreen()
                caught_fish = None
                hook_pos[1] = float(line_y)
                hook_x_anchor = float(HOOK_INITIAL_X)
        else:
            check_catch()

        # Balıkları güncelle ve çiz
        for f in fishes:
            f.update()
            f.draw(win)

        # Kancanın çizim koordinatlarını hesapla
        hook_x_draw = int(hook_pos[0] - hook_img.get_width() / 2)
        hook_y_draw = int(hook_pos[1] - hook_img.get_height() / 2)
        hook_connection_x = hook_x_draw + hook_img.get_width() / 2
        hook_connection_y = hook_y_draw + 5

        # İp ve Kanca Görselini çiz
        draw_zigzag_line(win, (line_x, line_y), (int(hook_connection_x), hook_connection_y), (255, 255, 255), 4,
                         time_counter)
        win.blit(hook_img, (hook_x_draw, hook_y_draw))

        # Yakalanmış balık etrafında Geri Bildirim Dairesi
        if caught_fish:
            circle_color = (0, 200, 0) if caught_fish.is_correct else (200, 0, 0)
            pygame.draw.circle(win, circle_color,
                               (int(hook_connection_x), int(hook_y_draw + hook_img.get_height() / 2)), 25, 3)

        # -------------------------------------
        # EĞİTSEL UI ÇİZİMİ
        # -------------------------------------
        question_bg = pygame.Rect(0, 0, WIDTH, 50)
        pygame.draw.rect(win, (0, 0, 0), question_bg)
        question_text_surf = FONT_QUESTION.render(f"SORU: {current_question}", True, (255, 255, 255))
        question_rect = question_text_surf.get_rect(center=(WIDTH // 2, 25))
        win.blit(question_text_surf, question_rect)
        score_text = FONT.render(f"Skor: {score}", True, (255, 255, 0))
        win.blit(score_text, (20, 20))

        if feedback_timer > 0:
            feedback_bg = pygame.Surface((450, 80), pygame.SRCALPHA)
            feedback_bg.fill((0, 0, 0, 180))
            feedback_surf = FONT_FEEDBACK.render(feedback_text, True, feedback_color)
            bg_rect = feedback_bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            feedback_rect = feedback_surf.get_rect(center=bg_rect.center)
            win.blit(feedback_bg, bg_rect)
            win.blit(feedback_surf, feedback_rect)
            feedback_timer -= 1

        pygame.display.update()

    # Oyun döngüsü bittiğinde Pygame'i kapat ve Seri Portu temizle
    if SERIAL_ENABLED and ser:
        ser.close()
        print("Seri port kapatıldı.")

    pygame.quit()
    sys.exit()

except Exception as e:
    # Hata oluşursa, konsola hatayı yazdırıp kapat ve Seri Portu temizle
    if 'ser' in locals() and ser and SERIAL_ENABLED:
        try:
            ser.close()
            print("Seri port hata sonrası kapatıldı.")
        except:
            pass

    print(f"Oyun başlatılırken veya çalışırken kritik bir hata oluştu: {e}")
    pygame.quit()
    sys.exit()