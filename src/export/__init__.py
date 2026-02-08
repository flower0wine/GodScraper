"""
数据导出模块
负责将数据导出为CSV和JSON格式
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


class DataExporter:
    """
    数据导出器

    负责将数据库中的数据导出为CSV和JSON格式
    """

    def __init__(self, db_manager):
        """
        初始化数据导出器

        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager

    def get_export_filename(self, channel: str, channel_name: str) -> str:
        """
        生成导出文件名

        Args:
            channel: 频道ID
            channel_name: 频道名称

        Returns:
            导出文件名
        """
        name = channel_name if channel_name != "Unknown" else "no_username"
        return f"{channel}_{name}"

    def export_to_csv(self, channel: str, channel_name: str = "Unknown") -> bool:
        """
        导出数据为CSV格式

        Args:
            channel: 频道标识符
            channel_name: 频道名称

        Returns:
            是否导出成功
        """
        try:
            conn = self.db_manager.get_connection(channel)
            cursor = conn.cursor()

            filename = self.get_export_filename(channel, channel_name)
            csv_file = Path(channel) / f"{filename}.csv"

            cursor.execute("SELECT * FROM messages ORDER BY date")
            columns = [description[0] for description in cursor.description]

            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)

                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    writer.writerows(rows)

            return True

        except Exception as e:
            print(f"CSV导出失败: {e}")
            return False

    def export_to_json(self, channel: str, channel_name: str = "Unknown") -> bool:
        """
        导出数据为JSON格式

        Args:
            channel: 频道标识符
            channel_name: 频道名称

        Returns:
            是否导出成功
        """
        try:
            conn = self.db_manager.get_connection(channel)
            cursor = conn.cursor()

            filename = self.get_export_filename(channel, channel_name)
            json_file = Path(channel) / f"{filename}.json"

            cursor.execute("SELECT * FROM messages ORDER BY date")
            columns = [description[0] for description in cursor.description]

            with open(json_file, "w", encoding="utf-8") as f:
                f.write("[\n")
                first_row = True

                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break

                    for row in rows:
                        if not first_row:
                            f.write(",\n")
                        else:
                            first_row = False

                        data = dict(zip(columns, row))
                        json.dump(data, f, ensure_ascii=False, indent=2)

                f.write("\n]")

            return True

        except Exception as e:
            print(f"JSON导出失败: {e}")
            return False

    def export_all_channels(
        self, channels: Dict[str, int], channel_names: Dict[str, str]
    ) -> None:
        """
        导出所有频道的数据

        Args:
            channels: 频道字典
            channel_names: 频道名称字典
        """
        if not channels:
            print("没有要导出的频道")
            return

        for channel in channels:
            print(f"导出频道 {channel} 的数据...")
            try:
                channel_name = channel_names.get(channel, "Unknown")

                csv_success = self.export_to_csv(channel, channel_name)
                json_success = self.export_to_json(channel, channel_name)

                if csv_success or json_success:
                    print(f"✅ 频道 {channel} 导出完成")
                else:
                    print(f"❌ 频道 {channel} 导出失败")

            except Exception as e:
                print(f"❌ 频道 {channel} 导出失败: {e}")


class ChannelListExporter:
    """
    频道列表导出器

    负责将频道列表导出为CSV格式
    """

    def __init__(self):
        """
        初始化频道列表导出器
        """
        self.csv_file = Path("channels_list.csv")

    def export(self, channels_data: List[Dict[str, Any]]) -> bool:
        """
        导出频道列表

        Args:
            channels_data: 频道数据列表

        Returns:
            是否导出成功
        """
        if not channels_data:
            return False

        try:
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "number",
                    "channel_name",
                    "channel_id",
                    "username",
                    "type",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(channels_data)

            print(f"\n✅ 频道列表已保存到 {self.csv_file}")
            return True

        except Exception as e:
            print(f"频道列表导出失败: {e}")
            return False
