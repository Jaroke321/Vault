from .base import BaseCommand
import datetime

class UpdateCommand(BaseCommand):

    call_str = "update" # Tells the prompt the string command in order to call this class
    mutates_commits = True

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        current_month = datetime.datetime.now().strftime("%Y-%m")              

        if not options:                                                                                                               
           self.usage()                                                                                          
        elif len(options) == 2:                                                                           
           self.sub_single_update(options, current_month)
        elif len(options) == 3:      
            self.sub_asset_value_update(options, current_month)                                                                        
        else:                                                                                                                         
           self.usage()

    ####################################
    # Sub-commands
    ####################################
    def sub_single_update(self, options, current_month):
        field_name, raw = options[0], options[1]
        success = False

        value = self._parse_float(raw)
        field_name_exists = self._is_a_field_name(field_name)

        if field_name_exists and value:

            self.commits.append([ field_name, current_month, value, "value" ])
            success = True

        else:
            print("[ERROR] Either field name doesnt exist yet, or the value was invalid")
            success = False
        
        return success

    def sub_asset_value_update(self, options, current_month):
        
        if self.sub_single_update(options, current_month):

            asset_value = self._parse_float(options[2])
            if asset_value:
                self.commits.append([ options[0], current_month, asset_value, "asset" ])
            
            else:
                print("[ERROR] Invalid asset number.")

    def usage(self):
        print("Usage: update | update <field_name> <value> | update <debt_field> <balance> <asset_value>")
