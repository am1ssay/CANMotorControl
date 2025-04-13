# server.py
import socket
import json
import threading
import time
from encoders import MultiEncoderMonitor
from step_motor import MoveStepMotor
from dc_motor import send_motor_command as dc_send_command
from enc_change_id import change_node_id as ecid_change_node_id


class RPIServer:

    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.encoder_monitor = MultiEncoderMonitor(channel='can0',
                                                   node_ids=[3, 4])
        self.clients = []
        self.monitoring = False
        self.lock = threading.Lock()

    def start(self):
        self.server.listen(5)
        print(f"Сервер запущен на {self.host}:{self.port}")
        threading.Thread(target=self.monitoring_loop, daemon=True).start()

        while True:
            client_socket, addr = self.server.accept()
            print(f"Подключение от {addr}")
            with self.lock:
                self.clients.append(client_socket)
            threading.Thread(target=self.handle_client,
                             args=(client_socket, )).start()

    def monitoring_loop(self):
        """Поток для мониторинга и рассылки данных"""
        while True:
            if self.monitoring and self.clients:
                data = self.encoder_monitor.get_current_data()
                message = {"type": "encoder_data", "data": data}
                with self.lock:
                    for client in self.clients.copy():
                        try:
                            client.send(json.dumps(message).encode('utf-8'))
                        except:
                            self.clients.remove(client)
            time.sleep(0.1)

    def handle_client(self, client_socket):
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                response = self.process_command(json.loads(data))
                client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            with self.lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()

    def process_command(self, command: dict) -> dict:
        try:
            cmd_type = command.get('type')
            args = command.get('args', {})

            if cmd_type == 'show_encoder':
                self.monitoring = True
                return {"status": "success", "message": "Мониторинг запущен"}

            elif cmd_type == 'change_id':
                current_id = args.get('current_id')
                new_id = args.get('new_id')
                if not (1 <= new_id <= 127):
                    return {
                        "status": "error",
                        "message": "Недопустимый новый ID"
                    }
                self.encoder_monitor.change_id_process(current_id, new_id)
                ecid_change_node_id(current_id, new_id)
                return {
                    "status": "success",
                    "message": f"ID изменен с {current_id} на {new_id}"
                }

            elif cmd_type == 'reset_position':
                node_id = args.get('node_id')
                success = self.encoder_monitor.reset_encoder_position(node_id)
                return {
                    "status": "success" if success else "error",
                    "message": f"Позиция энкодера {node_id} обнулена"
                }

            elif cmd_type == 'step_motor':
                power = args.get('power')
                direction = args.get('direction')
                steps = args.get('steps')
                with MoveStepMotor(channel='can0', node_id=0x101) as motor:
                    result = motor.send_motor_command(power, direction, steps)
                return {
                    "status": "success" if result else "error",
                    "message": "Команда шагового двигателя выполнена"
                }

            elif cmd_type == 'dc_motor':
                motor_id = args.get('motor_id')
                power_state = args.get('power_state')
                direction = args.get('direction')
                dc_send_command('can0', motor_id, power_state, direction)
                return {
                    "status": "success",
                    "message": "Команда DC двигателя отправлена"
                }

            else:
                return {"status": "error", "message": "Неизвестная команда"}

        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка выполнения: {str(e)}"
            }


if __name__ == "__main__":
    server = RPIServer()
    server.start()
