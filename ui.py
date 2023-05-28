from kivymd.app import MDApp
from kivymd.uix.button import MDRectangleFlatButton, MDFillRoundFlatIconButton, MDFloatingActionButton
from kivymd.uix.screen import MDScreen


class Example(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"  # "Purple", "Red"
        self.theme_cls.material_style = "M3"
        return (
            MDScreen(
                MDRectangleFlatButton(
                    text="Hello, World",
                    pos_hint={"center_x": 0.5, "center_y": 0.75},
                ),
                MDFillRoundFlatIconButton(
                    text="Hello, World",
                    icon="android",
                    pos_hint={"center_x": 0.5, "center_y": 0.25},
                ),
                MDFloatingActionButton(
                    icon="wrench-cog-outline",
                    pos_hint={"center_x": 0.9, "center_y": 0.9},
                )
            )
        )


Example().run()