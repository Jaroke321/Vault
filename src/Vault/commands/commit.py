from .base import BaseCommand
from rich.progress import track
import time

class CommitCommand(BaseCommand):

    call_str = "commit" # Tells the prompt the string command in order to call this class
    mutates_commits = True

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""            

        if not options:                                                                                                               
           self._commit_all()   
           return                                            
        else:                                                                                                                         
           self._commit_subset(options)

    def init_command(self) -> dict:

        return {self.call_str: self.entry_point}
    
    ####################################
    # Sub-commands
    ####################################
    def _commit_all(self):

        for current_commit in track(self.commits, description="Commiting Changes..."):
            time.sleep(0.5)
            if(current_commit[-1] == "value"):
                self.db.record_value(current_commit[0], current_commit[1], current_commit[2])
            elif(current_commit[-1] == "asset"):
                self.db.record_asset_value(current_commit[0], current_commit[1], current_commit[2])

        self.commits.clear()
    
    def _commit_subset(self, options):
        unique_options = set(options)
        successful_commits = []

        for commit_str in track(unique_options, description="Commiting Changes..."):
            time.sleep(0.5)

            try:
                commit_num = int(commit_str)

                if(commit_num > 0 and commit_num <= len(self.commits)):
                    current_commit = self.commits[commit_num-1]
                    if current_commit[-1] == "value":
                        self.db.record_value(current_commit[0], current_commit[1], current_commit[2])
                    else:
                        self.db.record_asset_value(current_commit[0], current_commit[1], current_commit[2])

                    successful_commits.append(commit_num-1)
                    
            except ValueError:
                pass

        # Remove from list everything we just commited
        for i in sorted(successful_commits, reverse=True):
            self.commits.pop(i)

    def usage(self):
        print("Usage: commit | commit <n> [n ...]")
