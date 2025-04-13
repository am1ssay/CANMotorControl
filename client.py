import tkinter as tk
from tkinter import messagebox, simpledialog
import socket
import json
import threading
import time


class MotorControlApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Управление моторами")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.monitoring = False
        self.buffer = []

        # Добавляем элемент для отображения данных энкодера
        self.encoder_frame = tk.LabelFrame(root, text="Данные энкодеров")
        self.encoder_scroll = tk.Scrollbar(self.encoder_frame)
        self.encoder_text = tk.Text(self.encoder_frame,
                                    height=10,
                                    width=60,
                                    state='disabled',
                                    yscrollcommand=self.encoder_scroll.set)
        self.encoder_frame.pack(pady=10)
        self.encoder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.encoder_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.encoder_scroll.config(command=self.encoder_text.yview)

        # Основные элементы интерфейса
        self.ip_frame = tk.Frame(root)
        self.ip_label = tk.Label(self.ip_frame, text="IP Raspberry Pi:")
        self.ip_entry = tk.Entry(self.ip_frame)
        self.connect_btn = tk.Button(self.ip_frame,
                                     text="Подключиться",
                                     command=self.connect)

        self.status_label = tk.Label(root,
                                     text="Статус: Не подключено",
                                     fg="red")
        self.command_frame = tk.Frame(root)

        # Кнопки управления
        self.change_id_btn = tk.Button(self.command_frame,
                                       text="Сменить ID энкодера",
                                       command=self.change_id)
        self.reset_btn = tk.Button(self.command_frame,
                                   text="Обнулить позицию",
                                   command=self.reset_position)
        self.step_motor_btn = tk.Button(self.command_frame,
                                        text="Шаговый двигатель",
                                        command=self.control_step_motor)
        self.dc_motor_btn = tk.Button(self.command_frame,
                                      text="DC двигатель",
                                      command=self.control_dc_motor)

        # Текстовое поле для вывода данных
        self.output_text = tk.Text(root, height=10, width=50, state='disabled')

        # Размещение элементов
        self.ip_frame.pack(pady=5)
        self.ip_label.pack(side=tk.LEFT)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.connect_btn.pack(side=tk.LEFT)
        self.status_label.pack(pady=5)
        self.command_frame.pack(pady=10)
        self.change_id_btn.pack(fill=tk.X, padx=5, pady=2)
        self.reset_btn.pack(fill=tk.X, padx=5, pady=2)
        self.step_motor_btn.pack(fill=tk.X, padx=5, pady=2)
        self.dc_motor_btn.pack(fill=tk.X, padx=5, pady=2)
        self.output_text.pack(padx=5, pady=5)

        # Блокировка элементов до подключения
        self.disable_controls()

    def disable_controls(self):
        """Блокировка элементов управления"""
        for widget in self.command_frame.winfo_children():
            widget.config(state=tk.DISABLED)

    def enable_controls(self):
        """Включение элементов управления"""
        for widget in self.command_frame.winfo_children():
            widget.config(state=tk.NORMAL)

    def connect(self):
        # Добавляем запуск мониторинга при подключении
        if self.connected:
            self.disconnect()
            return

        ip = self.ip_entry.get()
        try:
            self.socket.connect((ip, 5000))
            self.status_label.config(text=f"Статус: Подключено к {ip}",
                                     fg="green")
            self.connect_btn.config(text="Отключиться")
            self.enable_controls()
            self.connected = True
            # Запуск приема данных
            threading.Thread(target=self.receive_data, daemon=True).start()
            # Запуск мониторинга
            self.send_command({"type": "show_encoder"})
            self.monitoring = True
        except Exception as e:
            messagebox.showerror("Ошибка",
                                 f"Не удалось подключиться: {str(e)}")

    def disconnect(self):
        """Отключение от сервера"""
        if self.monitoring:
            self.send_command({"type": "stop_monitoring"})
            self.monitoring = False
        try:
            self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.status_label.config(text="Статус: Не подключено", fg="red")
            self.connect_btn.config(text="Подключиться")
            self.disable_controls()
            self.connected = False
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при отключении: {str(e)}")

    def send_command(self, command: dict):
        """Отправка команды на сервер"""
        try:
            self.socket.send(json.dumps(command).encode('utf-8'))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка отправки: {str(e)}")

    def receive_data(self):
        while self.connected:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if data:
                    message = json.loads(data)
                    if message.get('type') == 'encoder_data':
                        self.update_encoder_data(message['data'])
                    else:
                        self.update_output(message)
            except Exception as e:
                if self.connected:
                    messagebox.showerror("Ошибка",
                                         f"Ошибка приема данных: {str(e)}")
                break

    def update_encoder_data(self, data):
        """Обновление данных энкодеров в реальном времени"""
        self.encoder_text.config(state='normal')

        # Сохраняем позицию прокрутки
        scroll_pos = self.encoder_text.yview()

        # Блокируем обновление интерфейса на время модификации
        self.encoder_text.config(state='normal')
        self.encoder_text.delete(1.0, tk.END)

        self.buffer = []
        for node_id, values in data.items():
            current_time = time.time()
            current_norm, full_c, abs_angle, initial_abs, last_time, last_dir = values
            total_delta = abs_angle - initial_abs
            self.buffer.append(
                f"Node {node_id}:\n"
                f"  Текущий угол: {current_norm:9.2f}°\n"
                f"  Δ: {total_delta:+9.2f}°\n"
                f"  Последнее обновление: {current_time - last_time:.2f} с. назад\n"
                "-------------------------\n")

        # Вставляем все данные за одну операцию
        self.encoder_text.insert(tk.END, ''.join(self.buffer))

        # Восстанавливаем позицию прокрутки
        self.encoder_text.yview_moveto(scroll_pos[0])
        self.encoder_text.config(state='disabled')

    def update_output(self, response):
        """Обновление текстового поля вывода"""
        self.output_text.config(state='normal')
        self.output_text.insert(
            tk.END,
            f"[{response.get('type', 'info')}]: {response.get('message', '')}\n"
        )
        self.output_text.see(tk.END)
        self.output_text.config(state='disabled')

    def show_encoder(self):
        """Запрос данных энкодера"""
        self.send_command({"type": "show_encoder"})

    def change_id(self):
        """Диалог смены ID энкодера"""
        current_id = simpledialog.askinteger("Смена ID",
                                             "Текущий Node ID:",
                                             minvalue=1,
                                             maxvalue=127)
        if current_id is None:
            return
        new_id = simpledialog.askinteger("Смена ID",
                                         "Новый Node ID (1-127):",
                                         minvalue=1,
                                         maxvalue=127)
        if new_id is not None:
            self.send_command({
                "type": "change_id",
                "args": {
                    "current_id": current_id,
                    "new_id": new_id
                }
            })
            self.buffer.clear()

    def reset_position(self):
        """Диалог обнуления позиции"""
        node_id = simpledialog.askinteger("Обнулить позицию",
                                          "Node ID энкодера:",
                                          minvalue=1,
                                          maxvalue=127)
        if node_id is not None:
            self.send_command({
                "type": "reset_position",
                "args": {
                    "node_id": node_id
                }
            })

    def control_step_motor(self):
        """Диалог управления шаговым двигателем"""
        power = simpledialog.askinteger("Шаговый двигатель",
                                        "Питание (0/1):",
                                        minvalue=0,
                                        maxvalue=1)
        if power is None:
            return
        direction = simpledialog.askinteger("Шаговый двигатель",
                                            "Направление (0/1):",
                                            minvalue=0,
                                            maxvalue=1)
        if direction is None:
            return
        steps = simpledialog.askinteger("Шаговый двигатель",
                                        "Количество шагов:")
        if steps is not None:
            self.send_command({
                "type": "step_motor",
                "args": {
                    "power": power,
                    "direction": direction,
                    "steps": steps
                }
            })

    def control_dc_motor(self):
        """Диалог управления DC двигателем"""
        motor_id = simpledialog.askinteger("DC Двигатель",
                                           "ID мотора (2XX/3XX):",
                                           minvalue=200,
                                           maxvalue=399)
        if motor_id is None:
            return
        power_state = simpledialog.askinteger("DC Двигатель",
                                              "Питание (0/1):",
                                              minvalue=0,
                                              maxvalue=1)
        if power_state is None:
            return
        direction = simpledialog.askinteger("DC Двигатель",
                                            "Направление (0/1):",
                                            minvalue=0,
                                            maxvalue=1)
        if direction is not None:
            self.send_command({
                "type": "dc_motor",
                "args": {
                    "motor_id": motor_id,
                    "power_state": power_state,
                    "direction": direction
                }
            })


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorControlApp(root)
    root.mainloop()
