import can
import struct
import argparse
import time


class MoveStepMotor:

    def __init__(self, channel: str = 'can0', node_id=0x101):
        """
        Класс для отправки команд управления двигателем через CAN-интерфейс

        :param channel: CAN-интерфейс (например 'can0')
        :param node_id: ID узла в CAN-сети (по умолчанию 0x101)
        """
        self.node_id = node_id
        self.RESOLUTION = 1024

        try:
            self.bus = can.interface.Bus(interface='socketcan',
                                         channel=channel,
                                         bitrate=1000000)
        except Exception as e:
            raise ConnectionError(
                f"CAN interface initialization failed: {str(e)}")

    def send_motor_command(self, power: int, direction: int,
                           steps: int) -> bool:
        """
        Отправляет команду управления двигателем в CAN-шину и ожидает ответ

        :param power: вкл/выкл двигатель(0/1)
        :param direction: направление (0-против часовой, 1-по часовой)
        :param steps: количество шагов (0-1024)
        :return: True если отправка и ответ успешны, False в случае ошибки
        """
        # Проверка входных параметров
        if power not in (0, 1):
            raise ValueError("Power must be 0 or 1")
        if direction not in (0, 1):
            raise ValueError("Direction must be 0 or 1")
        if not 0 <= steps <= self.RESOLUTION:
            raise ValueError(f"Steps must be in 0-{self.RESOLUTION} range")

        # Подготовка данных
        data = struct.pack('>B B I', power, direction, steps)

        try:
            msg = can.Message(arbitration_id=self.node_id,
                              data=data,
                              is_extended_id=False)
            self.bus.send(msg)
            print(
                f"Sent CAN message: ID={hex(self.node_id)}, Data={data.hex()}")

            # Ожидание ответа с ID 0x101 и первым байтом 0xAA
            response_id = 0x101
            timeout = 1.0  # Таймаут ожидания в секундах
            start_time = time.time()
            response_received = False

            while time.time() - start_time < timeout:
                remaining_timeout = timeout - (time.time() - start_time)
                response_msg = self.bus.recv(remaining_timeout)

                if response_msg and response_msg.arbitration_id == response_id:
                    if len(response_msg.data
                           ) >= 1 and response_msg.data[0] == 0xAA:
                        print(
                            f"Received response: ID={hex(response_id)}, Data={response_msg.data.hex()}"
                        )
                        msg = can.Message(
                            arbitration_id=self.node_id,
                            data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                            is_extended_id=False)
                        self.bus.send(msg)
                        response_received = True
                        break

            if not response_received:
                print("Timeout waiting for response")
                return False

            return True

        except can.CanError as e:
            print(f"CAN send error: {e}")
            return False

    def close(self):
        """Корректно закрывает CAN-интерфейс"""
        if hasattr(self, 'bus') and self.bus:
            self.bus.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():

    try:
        with MoveStepMotor(channel='can0', node_id=0x101) as monitor:
            if monitor.send_motor_command(1, 1, 100):
                print("Command sent and response received successfully")
            else:
                print("Command sent but no response received")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
