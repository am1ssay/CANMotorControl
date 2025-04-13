import can
import signal
import sys
import time
import select
import struct
import json


class MultiEncoderMonitor:

    def __init__(self, channel='can0', node_ids=None):
        # Загрузка конфигурации
        self.config_file = 'encoder_config.json'
        config = self.load_config()
        
        # Инициализация параметров энкодера из конфига
        self.RESOLUTION = config.get('resolution', 1024)
        self.FULL_CIRCLE = config.get('full_circle', 360.0)
        self.DEGREES_PER_STEP = self.FULL_CIRCLE / self.RESOLUTION
        
        # Инициализация node_ids
        self.node_ids = node_ids if node_ids is not None else config.get('node_ids', [1])
        
        # Остальная инициализация
        self.bus = can.interface.Bus(interface='socketcan',
                                     channel=channel,
                                     bitrate=1000000)
        self.expected_pdo_ids = []
        for node_id in self.node_ids:
            self.expected_pdo_ids.append(0x180 + node_id)
            self.expected_pdo_ids.append(0x280 + node_id)
        self.encoder_states = {}
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = True
        self.output = []
        
        # Сохраняем конфиг при изменении параметров
        self.save_config()

    def save_config(self):
        """Сохранение полной конфигурации в файл"""
        config = {
            'node_ids': self.node_ids,
            'encoder_params': {
                'resolution': self.RESOLUTION,
                'full_circle': self.FULL_CIRCLE
            }
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")

    def load_config(self):
        """Загрузка полной конфигурации из файла"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Обработка старых конфигов без encoder_params
                if 'encoder_params' not in config:
                    return {
                        'node_ids': config.get('node_ids', [1]),
                        'resolution': 1024,
                        'full_circle': 360.0
                    }
                return {
                    'node_ids': config.get('node_ids', [1]),
                    'resolution': config['encoder_params'].get('resolution', 1024),
                    'full_circle': config['encoder_params'].get('full_circle', 360.0)
                }
        except FileNotFoundError:
            return {
                'node_ids': [1],
                'resolution': 1024,
                'full_circle': 360.0
            }
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            return {
                'node_ids': [1],
                'resolution': 1024,
                'full_circle': 360.0
            }

    def change_id_process(self, current_id, new_id):
        if current_id != new_id and current_id in self.node_ids:
            # Удаляем старый ID из всех структур
            self.node_ids.remove(current_id)
            if current_id in self.encoder_states:
                del self.encoder_states[current_id]  # Удаляем старое состояние
            # Добавляем новый ID
            self.node_ids.append(new_id)
            # Пересоздаем ожидаемые COB-ID
            self.expected_pdo_ids = []
            for node_id in self.node_ids:
                self.expected_pdo_ids.append(0x180 + node_id)
                self.expected_pdo_ids.append(0x280 + node_id)
            # Очищаем вывод
            self.output = []

    def bytes_to_angle(self, data):
        """Конвертация little-endian в нормализованный угол"""
        if len(data) < 2:
            return None
        raw = data[0] | (data[1] << 8)
        return (raw * self.DEGREES_PER_STEP) % 360

    def get_current_data(self):
        """Возвращает актуальные данные энкодеров"""
        return self.encoder_states.copy()

    def calculate_delta(self, node_id, current_normalized):
        """Вычисление дельты с учетом полных оборотов и направления"""
        if node_id not in self.encoder_states:
            initial_abs = current_normalized
            self.encoder_states[node_id] = (
                current_normalized,
                0,
                current_normalized,
                initial_abs,
                time.time(),
                0  # last_direction
            )
            return 0.0

        prev_norm, full_circles, abs_angle, initial_abs, last_time, last_dir = self.encoder_states[
            node_id]
        delta = current_normalized - prev_norm

        # Коррекция циклического перехода
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        direction = 0
        if delta != 0 and abs(delta) > 5:
            direction = 1 if delta > 0 else -1

        direction_changed = (direction != 0 and direction != last_dir)

        if direction != 0:
            # Обновление оборотов при переходе через 0/360
            if direction == 1 and current_normalized < prev_norm:
                full_circles += 1
            elif direction == -1 and current_normalized > prev_norm:
                full_circles -= 1

        absolute_angle = full_circles * 360 + current_normalized

        reset_needed = False
        if delta != 0 and direction_changed:
            reset_needed = True

        if reset_needed:
            initial_abs = absolute_angle
            last_time = time.time()
            last_dir = direction
        else:
            last_time = time.time() if delta != 0 else last_time

        self.encoder_states[node_id] = (current_normalized, full_circles,
                                        absolute_angle, initial_abs, last_time,
                                        last_dir)
        return delta if not reset_needed else 0.0

    def signal_handler(self, sig, frame):
        print("\nЗавершение работы...")
        self.running = False
        self.bus.shutdown()
        sys.exit(0)

    def reset_encoder_position(self, node_id):
        """Сброс позиции через Preset Value для конкретного энкодера"""
        index = 0x6003
        subindex = 0x00
        value = 0x00000000
        data = [
            0x23,
            index.to_bytes(2, 'little')[0],
            index.to_bytes(2, 'little')[1], subindex, (value & 0xFF),
            ((value >> 8) & 0xFF), ((value >> 16) & 0xFF),
            ((value >> 24) & 0xFF)
        ]
        cob_id = 0x600 + node_id
        try:
            msg = can.Message(arbitration_id=cob_id,
                              data=data,
                              is_extended_id=False)
            self.bus.send(msg)
            response = self.bus.recv(timeout=0.5)
            if response and response.arbitration_id == 0x580 + node_id:
                if response.data[0] == 0x60:
                    # Сбрасываем внутреннее состояние
                    self.encoder_states[node_id] = (0.0, 0, 0.0, 0.0,
                                                    time.time(), 0)
                    return True
                else:
                    print(
                        f"❌ Ошибка SDO для node {node_id}: код {response.data[0]:02X}"
                    )
        except Exception as e:
            print(f"❌ Ошибка отправки SDO для node {node_id}: {str(e)}")
        return False


    def start_monitoring(self):
        print(
            "Мониторинг энкодеров. 's' - сброс всех, 'h' - движение. Ctrl+C для выхода."
        )
        print("-" * 60)
        try:
            while self.running:
                # Обработка входящих сообщений
                msg = self.bus.recv(timeout=0.1)
                if msg and msg.arbitration_id in self.expected_pdo_ids:
                    node_id = msg.arbitration_id - 0x180  # Определяем node_id по TPDO1
                    if node_id not in self.node_ids:
                        node_id = msg.arbitration_id - 0x280  # Проверяем TPDO2
                    if node_id in self.node_ids:
                        current_angle = self.bytes_to_angle(msg.data)
                        if current_angle is not None:
                            self.calculate_delta(node_id, current_angle)

                # Обработка ввода с клавиатуры
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    key = sys.stdin.read(1)
                    if key == 's':
                        for node_id in self.node_ids:
                            self.reset_encoder_position(node_id)
                    elif key == 'h':
                        for node_id in self.node_ids:
                            self.move(node_id, 0, 1, 100)

                # Формирование вывода
                current_time = time.time()
                self.output = []
                for node_id in sorted(self.encoder_states.keys()):
                    state = self.encoder_states[node_id]
                    current_norm, full_c, abs_angle, initial_abs, last_time, _ = state

                    # Проверка таймаута
                    if current_time - last_time > 1:
                        self.encoder_states[node_id] = (current_norm, full_c,
                                                        abs_angle, abs_angle,
                                                        current_time, 0)

                    total_delta = abs_angle - initial_abs
                    output_line = (
                        f"Node {node_id}: {current_norm:9.2f}° "
                        f"(Δ{total_delta:+9.2f}°) Last: {current_time - last_time:.2f}s"
                    )
                    self.output.append(output_line)

                print("\r" + " | ".join(self.output), end='', flush=True)
        except KeyboardInterrupt:
            self.signal_handler(None, None)


if __name__ == "__main__":
    monitor = MultiEncoderMonitor(channel='can0')
    monitor.start_monitoring()
