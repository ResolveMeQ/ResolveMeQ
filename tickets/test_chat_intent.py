from django.test import TestCase

from tickets.chat_intent import user_message_indicates_resolution_success


class ResolutionSuccessIntentTest(TestCase):
    def test_it_worked_variants(self):
        self.assertTrue(user_message_indicates_resolution_success("it has worked o haha"))
        self.assertTrue(user_message_indicates_resolution_success("it worked!"))
        self.assertTrue(user_message_indicates_resolution_success("That fixed it"))
        self.assertTrue(user_message_indicates_resolution_success("all good now thanks"))

    def test_not_resolution_success(self):
        self.assertFalse(user_message_indicates_resolution_success("it still does not work"))
        self.assertFalse(user_message_indicates_resolution_success("wifi worked before but not now"))
        self.assertFalse(user_message_indicates_resolution_success(""))
        self.assertFalse(
            user_message_indicates_resolution_success(
                "it worked but now something else broke and the screen is blue again with error code 0x0001"
            )
        )
